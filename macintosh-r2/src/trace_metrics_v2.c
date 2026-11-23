#include "trace_metrics_v2.h"
#include <inttypes.h>
#include <limits.h>
#include <string.h>

/* All interval accounting is exclusive: the top ISR wins over the suspended task.
 * Unobserved scheduler intervals are UNKNOWN, never automatically called idle. */
static void warning(m2_engine *m, const char *code, int id, uint64_t ts) {
 ++m->warnings; m->had_error = 1;
 fprintf(m->out, "M2_WARN,code=%s,id=%d,ts_us=%" PRIu64 "\n",code,id,ts);
}
void m2_init(m2_engine *m, FILE *out, uint64_t window) {
 memset(m,0,sizeof(*m)); m->running=-1; m->idle_id=-1; m->out=out; m->window_us=window;
 fprintf(out,"M2_FORMAT,version=2,timebase=normalized_us,window_us=%" PRIu64
             ",model=single_core_exclusive,unknown_not_idle=1\n",window);
}
int m2_config_task(m2_engine *m, int id) {
 if(id<0||id>=M2_MAX_TASKS)return -1;
 m->tasks[id].configured=1;
 return 0;
}
int m2_config_idle(m2_engine *m, int id) {
 if(m2_config_task(m,id)!=0||m->idle_id>=0)return -1;
 m->idle_id=id;return 0;
}
int m2_config_isr(m2_engine *m, int id, uint64_t budget) {
 if(id<0||id>=M2_MAX_ISRS||budget==0)return -1;
 m->isrs[id].configured=1;m->isrs[id].budget_us=budget;return 0;
}
int m2_parse_type(const char *name,m2_event_type *type) {
 static const char *names[]={"RELEASE","SWITCH_IN","SWITCH_OUT","COMPLETE","BLOCK",
                              "UNBLOCK","ISR_ENTER","ISR_EXIT","GAP"};
 for(int i=0;i<9;i++)if(strcmp(name,names[i])==0){*type=(m2_event_type)i;return 0;}
 return -1;
}
static int emit_window(m2_engine *m, uint64_t end) {
 uint64_t duration=end-m->window_start;
 uint64_t check=m->w_tasks+m->w_isrs+m->w_idle+m->w_unknown;
 const char *status=m->w_gap?"GAP":(m->w_unknown?"PARTIAL":"COMPLETE");
 if(check!=duration){warning(m,"WINDOW_ACCOUNTING_FAILURE",-1,end);return -1;}
 fprintf(m->out,"M2_WINDOW,start_us=%" PRIu64 ",end_us=%" PRIu64
  ",elapsed_us=%" PRIu64 ",task_us=%" PRIu64 ",isr_us=%" PRIu64
  ",idle_us=%" PRIu64 ",unknown_us=%" PRIu64
  ",busy_lower_pct=%.3f,quality=%s\n",
  m->window_start,end,duration,m->w_tasks,m->w_isrs,m->w_idle,m->w_unknown,
  duration?100.0*(double)(m->w_tasks+m->w_isrs)/(double)duration:0.0,status);
 for(int i=0;i<M2_MAX_TASKS;i++)if(m->w_task[i])
   fprintf(m->out,"M2_WINDOW_TASK,start_us=%" PRIu64 ",end_us=%" PRIu64
    ",id=%d,exclusive_us=%" PRIu64 "\n",m->window_start,end,i,m->w_task[i]);
 for(int i=0;i<M2_MAX_ISRS;i++)if(m->w_isr[i])
   fprintf(m->out,"M2_WINDOW_ISR,start_us=%" PRIu64 ",end_us=%" PRIu64
    ",id=%d,exclusive_us=%" PRIu64 "\n",m->window_start,end,i,m->w_isr[i]);
 memset(m->w_task,0,sizeof(m->w_task));
 memset(m->w_isr,0,sizeof(m->w_isr));
 m->w_tasks=m->w_isrs=m->w_idle=m->w_unknown=0;
 m->w_gap=0; m->windows++;m->window_start=end;
 return 0;
}
static int advance(m2_engine *m,uint64_t ts,int gap_before) {
 if(!m->started) {
   if(m->window_us==0||ts>UINT64_MAX-m->window_us)return -1;
   m->first=ts;m->previous=ts;m->window_start=ts;m->window_end=ts+m->window_us;
   m->started=1;
   return 0;
 }
 if(ts<m->previous){warning(m,"NON_MONOTONIC_TIMESTAMP",-1,ts);return -1;}
 if(gap_before)m->w_gap=1;
 for(uint64_t p=m->previous;p<ts;) {
   uint64_t end=ts<m->window_end?ts:m->window_end;
   uint64_t dt=end-p;
   if(m->windows>=M2_MAX_WINDOWS) {
     warning(m,"WINDOW_LIMIT_REACHED",-1,p);return -1;
   }
   if(gap_before) {
      m->w_unknown+=dt;m->unknown_total+=dt;
   }else if(m->depth>0) {
      int id=m->stack[m->depth-1].id;
      m->w_isrs+=dt;m->isr_total+=dt;
      m->w_isr[id]+=dt;m->isrs[id].exclusive_us+=dt;
   }else if(m->running==m->idle_id && m->idle_id>=0) {
      m->w_idle+=dt;m->idle_total+=dt;
   }else if(m->running>=0) {
      int id=m->running;
      m->w_tasks+=dt;m->task_total+=dt;
      m->w_task[id]+=dt;m->tasks[id].cpu_us+=dt;
   }else {
      m->w_unknown+=dt;m->unknown_total+=dt;
   }
   p=end;
   if(p==m->window_end) {
     if(emit_window(m,p)!=0)return -1;
     if(p>UINT64_MAX-m->window_us){warning(m,"WINDOW_END_OVERFLOW",-1,p);return -1;}
     m->window_end=p+m->window_us;
   }
 }
 m->previous=ts;
 return 0;
}
static void invalid_state(m2_engine *m,const char *reason,int id,uint64_t ts){
 warning(m,reason,id,ts);
 m->running=-1;
 for(int i=0;i<M2_MAX_TASKS;i++){m->tasks[i].active=0;m->tasks[i].blocked=0;}
 for(int i=0;i<m->depth;i++)m->isrs[m->stack[i].id].incomplete++;
 m->depth=0;
}
int m2_feed(m2_engine *m,const m2_event *ev) {
 if(!ev||ev->type<M2_RELEASE||ev->type>M2_GAP)return -1;
 if(advance(m,ev->ts,ev->type==M2_GAP)!=0)return -1;
 int id=ev->id;
 if(ev->type==M2_GAP){
   ++m->gaps; m->w_gap=1;
   m->running=-1;
   for(int i=0;i<M2_MAX_TASKS;i++){m->tasks[i].active=0;m->tasks[i].blocked=0;}
   for(int i=0;i<m->depth;i++)m->isrs[m->stack[i].id].incomplete++;
   m->depth=0;
   fprintf(m->out,"M2_GAP,ts_us=%" PRIu64 ",quality=INVALIDATE_ALL_ACTIVE\n",ev->ts);
   return 0;
 }
 if(ev->type==M2_ISR_ENTER){
   if(id<0||id>=M2_MAX_ISRS||!m->isrs[id].configured||m->depth>=M2_MAX_DEPTH){
     invalid_state(m,"INVALID_ISR_ENTER",id,ev->ts);return -1;
   }
   m->stack[m->depth].id=id;m->stack[m->depth].entered_us=ev->ts;
   m->depth++;return 0;
 }
 if(ev->type==M2_ISR_EXIT) {
   if(m->depth<=0||id!=m->stack[m->depth-1].id){
     invalid_state(m,"UNMATCHED_ISR_EXIT",id,ev->ts);return -1;
   }
   m->depth--;
   uint64_t inclusive=ev->ts-m->stack[m->depth].entered_us;
   m2_isr *s=&m->isrs[id];
   ++s->calls;s->inclusive_us+=inclusive;
   if(inclusive>s->max_us)s->max_us=inclusive;
   if(inclusive>s->budget_us){
     ++s->over_budget;
     fprintf(m->out,"M2_WARN,code=ISR_OVER_BUDGET,id=%d,ts_us=%" PRIu64
     ",measured_us=%" PRIu64 ",limit_us=%" PRIu64 "\n",id,ev->ts,inclusive,s->budget_us);
     ++m->warnings;
   }
   fprintf(m->out,"M2_ISR_CALL,id=%d,start_us=%" PRIu64
        ",end_us=%" PRIu64 ",inclusive_us=%" PRIu64
        ",quality=COMPLETE\n",id,m->stack[m->depth].entered_us,ev->ts,inclusive);
   return 0;
 }
 if(id<0||id>=M2_MAX_TASKS||!m->tasks[id].configured) {
   invalid_state(m,"UNKNOWN_TASK",id,ev->ts);return -1;
 }
 m2_task *t=&m->tasks[id];
 switch(ev->type) {
 case M2_RELEASE:
   if(id==m->idle_id||t->active){
     invalid_state(m,"INVALID_RELEASE",id,ev->ts);return -1;
   }
   t->active=1;t->blocked=0;break;
 case M2_SWITCH_IN:
   if(m->depth||m->running>=0||(id!=m->idle_id&&(!t->active||t->blocked))){
     invalid_state(m,"INVALID_SWITCH_IN",id,ev->ts);return -1;
   }
   m->running=id;break;
 case M2_SWITCH_OUT:
   if(m->depth||m->running!=id){
     invalid_state(m,"INVALID_SWITCH_OUT",id,ev->ts);return -1;
   }
   m->running=-1;break;
 case M2_BLOCK:
   if(m->depth||id==m->idle_id||!t->active||t->blocked){
     invalid_state(m,"INVALID_BLOCK",id,ev->ts);return -1;
   }
   if(m->running==id)m->running=-1;
   t->blocked=1;break;
 case M2_UNBLOCK:
   if(id==m->idle_id||!t->active||!t->blocked){
     invalid_state(m,"INVALID_UNBLOCK",id,ev->ts);return -1;
   }
   t->blocked=0;break;
 case M2_COMPLETE:
   if(m->depth||id==m->idle_id||!t->active||t->blocked){
     invalid_state(m,"INVALID_COMPLETE",id,ev->ts);return -1;
   }
   if(m->running==id)m->running=-1;
   t->active=0;break;
 default:return -1;
 }
 return 0;
}
int m2_finish(m2_engine *m){
 if(m->started && m->previous>m->window_start)
   if(emit_window(m,m->previous)!=0)return -1;
 for(int i=0;i<m->depth;i++) {
   m->isrs[m->stack[i].id].incomplete++;
   warning(m,"UNCLOSED_ISR",m->stack[i].id,m->previous);
 }
 for(int id=0;id<M2_MAX_TASKS;id++)if(m->tasks[id].configured){
   fprintf(m->out,"M2_TASK_SUMMARY,id=%d,exclusive_us=%" PRIu64
    ",role=%s\n",id,id==m->idle_id?m->idle_total:m->tasks[id].cpu_us,
       id==m->idle_id?"IDLE":"TASK");
 }
 for(int id=0;id<M2_MAX_ISRS;id++)if(m->isrs[id].configured){
   m2_isr *s=&m->isrs[id];
   fprintf(m->out,"M2_ISR_SUMMARY,id=%d,calls=%" PRIu64
   ",inclusive_us=%" PRIu64 ",exclusive_us=%" PRIu64
   ",max_inclusive_us=%" PRIu64 ",over_budget=%" PRIu64
   ",incomplete=%" PRIu64 "\n",id,s->calls,s->inclusive_us,
   s->exclusive_us,s->max_us,s->over_budget,s->incomplete);
 }
 uint64_t duration=m->started?m->previous-m->first:0;
 fprintf(m->out,"M2_SESSION,elapsed_us=%" PRIu64
  ",task_us=%" PRIu64 ",isr_us=%" PRIu64
  ",idle_us=%" PRIu64 ",unknown_us=%" PRIu64
  ",gaps=%" PRIu64 ",warnings=%" PRIu64
  ",windows=%" PRIu64 ",quality=%s\n",
  duration,m->task_total,m->isr_total,m->idle_total,m->unknown_total,
  m->gaps,m->warnings,m->windows,
  m->had_error?"ERROR":m->gaps?"GAP":m->unknown_total?"PARTIAL":"COMPLETE");
 if(m->task_total+m->isr_total+m->idle_total+m->unknown_total!=duration){
   warning(m,"SESSION_ACCOUNTING_FAILURE",-1,m->previous);return -1;
 }
 return m->had_error?1:0;
}
