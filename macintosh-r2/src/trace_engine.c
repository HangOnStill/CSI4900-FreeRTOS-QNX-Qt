#include "trace_engine.h"
#include <inttypes.h>
#include <string.h>
#include <stdlib.h>

static void warn(trace_engine *e,const char *code,int id,uint64_t ts,uint64_t value,uint64_t limit){
 ++e->warnings;
 fprintf(e->out,"WARN,%s,%d,%" PRIu64 ",%" PRIu64 ",%" PRIu64 "\n",code,id,ts,value,limit);
}
static void stop_running(trace_engine *e,uint64_t ts,int preempt){
 int id=e->running_task;
 if(id<0) return;
 trace_task *t=&e->tasks[id];
 if(t->active && t->running){
   t->cpu_current_us += ts-t->run_start_us;
   if(preempt){ ++t->preempt_current; }
   t->running=0;
 }
 e->running_task=-1;
}
static void invalidate_task(trace_engine *e, trace_task *t,uint64_t ts,const char *reason){
 if(t->active){ ++t->invalid_activations; warn(e,reason,t->id,ts,0,0); }
 if(e->running_task==t->id) e->running_task=-1;
 t->active=0;t->running=0;t->blocked=0;
 t->cpu_current_us=0;t->block_current_us=0;t->preempt_current=0;
}
void trace_engine_init(trace_engine *e,FILE *out){
 int i;
 memset(e,0,sizeof(*e));e->running_task=-1;e->out=out;
 for(i=0;i<TRACE_MAX_TASKS;i++)e->tasks[i].id=i;
 for(i=0;i<TRACE_MAX_ISRS;i++)e->isrs[i].id=i;
 /* Records use distinct prefixes; summary rows have explicit key=value fields. */
}
int trace_config_task(trace_engine *e,int id,uint64_t period,uint64_t deadline,uint64_t jitter,uint64_t block){
 trace_task *t;
 if(id<0||id>=TRACE_MAX_TASKS||!period||!deadline)return -1;
 t=&e->tasks[id];t->configured=1;t->period_us=period;t->deadline_us=deadline;
 t->jitter_bound_us=jitter;t->block_bound_us=block;return 0;
}
int trace_config_isr(trace_engine *e,int id,uint64_t budget){
 if(id<0||id>=TRACE_MAX_ISRS||!budget)return -1;
 e->isrs[id].configured=1;e->isrs[id].budget_us=budget;return 0;
}
int trace_feed(trace_engine *e,const trace_event *v){
 trace_task *t=NULL;
 uint64_t dt, jitter;
 int i;
 if(e->started && v->ts_us<e->last_ts){ warn(e,"TIME_REVERSED",v->id,v->ts_us,0,0);return -1; }
 if(!e->started){ e->started=1;e->first_ts=v->ts_us; }
 e->last_ts=v->ts_us;
 if(v->type==EV_GAP){
   stop_running(e,v->ts_us,0);e->gap_seen=1;++e->gaps;
   for(i=0;i<TRACE_MAX_TASKS;i++){
      invalidate_task(e,&e->tasks[i],v->ts_us,"DISCARDED_BY_GAP");
      e->tasks[i].has_last_release=0;
   }
   e->depth=0;warn(e,"TRACE_GAP",-1,v->ts_us,0,0);return 0;
 }
 if(v->type==EV_ISR_ENTER){
   if(v->id<0||v->id>=TRACE_MAX_ISRS||!e->isrs[v->id].configured){warn(e,"UNKNOWN_ISR",v->id,v->ts_us,0,0);return -1;}
   if(e->depth>=TRACE_MAX_ISR_DEPTH){warn(e,"ISR_STACK_OVERFLOW",v->id,v->ts_us,0,0);return -1;}
   if(e->depth==0)stop_running(e,v->ts_us,0);
   e->stack[e->depth].id=v->id;e->stack[e->depth].entered_us=v->ts_us;++e->depth;return 0;
 }
 if(v->type==EV_ISR_EXIT){
   trace_isr *s;
   if(e->depth==0 || e->stack[e->depth-1].id!=v->id){ warn(e,"ISR_UNMATCHED_EXIT",v->id,v->ts_us,0,0);return -1; }
   --e->depth;dt=v->ts_us-e->stack[e->depth].entered_us;
   s=&e->isrs[v->id];++s->calls;s->total_duration_us+=dt;
   if(dt>s->max_duration_us)s->max_duration_us=dt;
   if(dt>s->budget_us){++s->over_budget;warn(e,"ISR_OVER_BUDGET",v->id,v->ts_us,dt,s->budget_us);}
   fprintf(e->out,"ISR_DURATION,ISR,%d,%" PRIu64 ",%" PRIu64 ",%" PRIu64 "\n",v->id,v->ts_us,dt,s->budget_us);
   return 0;
 }
 if(v->id<0||v->id>=TRACE_MAX_TASKS||!e->tasks[v->id].configured){warn(e,"UNKNOWN_TASK",v->id,v->ts_us,0,0);return -1;}
 t=&e->tasks[v->id];
 switch(v->type){
 case EV_RELEASE:
   if(t->active){warn(e,"OVERLAPPING_RELEASE",t->id,v->ts_us,0,0);invalidate_task(e,t,v->ts_us,"DISCARDED_OVERLAP");t->has_last_release=0;}
   if(t->has_last_release){
     dt=v->ts_us-t->last_release_us;
     jitter=dt>t->period_us?dt-t->period_us:t->period_us-dt;
     if(jitter>t->jitter_bound_us){++t->jitter_violations;warn(e,"RELEASE_JITTER",t->id,v->ts_us,jitter,t->jitter_bound_us);}
   }
   t->has_last_release=1;t->last_release_us=v->ts_us;
   t->release_us=v->ts_us;t->active=1;t->running=0;t->blocked=0;
   t->cpu_current_us=0;t->block_current_us=0;t->preempt_current=0;
   break;
 case EV_SWITCH_IN:
   if(e->depth||!t->active||t->blocked||e->running_task!=-1){warn(e,"INVALID_SWITCH_IN",t->id,v->ts_us,0,0);return -1;}
   e->running_task=t->id;t->running=1;t->run_start_us=v->ts_us;break;
 case EV_SWITCH_OUT:
   if(e->depth||!t->running||e->running_task!=t->id){warn(e,"INVALID_SWITCH_OUT",t->id,v->ts_us,0,0);return -1;}
   stop_running(e,v->ts_us,1);break;
 case EV_BLOCK:
   if(!t->active||t->blocked||e->depth){warn(e,"INVALID_BLOCK",t->id,v->ts_us,0,0);return -1;}
   if(t->running)stop_running(e,v->ts_us,0);
   t->blocked=1;t->block_start_us=v->ts_us;break;
 case EV_UNBLOCK:
   if(!t->active||!t->blocked){warn(e,"INVALID_UNBLOCK",t->id,v->ts_us,0,0);return -1;}
   dt=v->ts_us-t->block_start_us;t->block_current_us+=dt;t->blocked=0;
   if(dt>t->block_bound_us){++t->block_violations;warn(e,"BLOCK_TOO_LONG",t->id,v->ts_us,dt,t->block_bound_us);}
   break;
 case EV_COMPLETE:
   if(!t->active||t->blocked||e->depth){warn(e,"INVALID_COMPLETE",t->id,v->ts_us,0,0);return -1;}
   if(t->running)stop_running(e,v->ts_us,0);
   dt=v->ts_us-t->release_us;
   ++t->completions;t->total_cpu_us+=t->cpu_current_us;t->total_response_us+=dt;t->total_block_us+=t->block_current_us;
   t->preemptions+=t->preempt_current;
   if(dt>t->deadline_us){++t->deadline_misses;warn(e,"DEADLINE_MISS",t->id,v->ts_us,dt,t->deadline_us);}
   fprintf(e->out,"ACTIVATION,task,%d,%" PRIu64 ",%" PRIu64 ",%" PRIu64 "\n",t->id,v->ts_us,dt,t->cpu_current_us);
   t->active=0;t->running=0;break;
 default:return -1;
 }
 return 0;
}
void trace_finish(trace_engine *e){
 int i;
 for(i=0;i<TRACE_MAX_TASKS;i++) if(e->tasks[i].active)invalidate_task(e,&e->tasks[i],e->last_ts,"INCOMPLETE_ACTIVATION");
 for(i=0;i<TRACE_MAX_TASKS;i++){
   trace_task *t=&e->tasks[i];
   if(!t->configured)continue;
   fprintf(e->out,"TASK_SUMMARY,id=%d,valid=%" PRIu64 ",invalid=%" PRIu64 ",cpu_us=%" PRIu64 ",response_us=%" PRIu64 ",blocked_us=%" PRIu64 ",deadline_misses=%" PRIu64 ",jitter_violations=%" PRIu64 ",block_violations=%" PRIu64 ",preemptions=%" PRIu64 "\n",
      t->id,t->completions,t->invalid_activations,t->total_cpu_us,t->total_response_us,t->total_block_us,t->deadline_misses,t->jitter_violations,t->block_violations,t->preemptions);
 }
 for(i=0;i<TRACE_MAX_ISRS;i++){
   trace_isr *s=&e->isrs[i];if(!s->configured)continue;
   fprintf(e->out,"ISR_SUMMARY,id=%d,calls=%" PRIu64 ",total_duration_us=%" PRIu64 ",max_duration_us=%" PRIu64 ",over_budget=%" PRIu64 "\n",s->id,s->calls,s->total_duration_us,s->max_duration_us,s->over_budget);
 }
 if(e->started && e->last_ts>e->first_ts && !e->gap_seen){
  uint64_t window=e->last_ts-e->first_ts;
  for(i=0;i<TRACE_MAX_TASKS;i++){
   trace_task *t=&e->tasks[i];
   if(!t->configured)continue;
   if(t->invalid_activations){
    fprintf(e->out,"CPU_UTIL,id=%d,scope=FULL_SESSION,status=UNAVAILABLE_INCOMPLETE\n",t->id);
   }else{
    double percent=100.0*(double)t->total_cpu_us/(double)window;
    fprintf(e->out,"CPU_UTIL,id=%d,scope=FULL_SESSION,window_us=%" PRIu64 ",percent=%.3f\n",t->id,window,percent);
   }
  }
 }
 fprintf(e->out,"SESSION,gaps=%" PRIu64 ",warnings=%" PRIu64 ",time_span_us=%" PRIu64 ",utilization=%s\n",
 e->gaps,e->warnings,e->started?e->last_ts-e->first_ts:0,e->gap_seen?"UNAVAILABLE_DUE_TO_GAP":"FULL_SESSION_ONLY");
}
int trace_parse_type(const char *s,trace_event_type *out){
 const char *names[]={"RELEASE","SWITCH_IN","SWITCH_OUT","COMPLETE","BLOCK","UNBLOCK","ISR_ENTER","ISR_EXIT","GAP"};
 int i;for(i=0;i<9;i++)if(strcmp(s,names[i])==0){*out=(trace_event_type)i;return 0;}
 return -1;
}
