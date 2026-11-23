/* Portable C11 test adapter; NOT Xavier's binary UART frame decoder. */
#include "trace_engine.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include <errno.h>
#include <ctype.h>

static int read_config(trace_engine *eng,const char *path){
 FILE *f=fopen(path,"r");char line[512];int line_n=0,errors=0;
 if(!f){perror(path);return -1;}
 while(fgets(line,sizeof(line),f)){
   int id;uint64_t a,b,c,d;char tag[32];++line_n;
   if(line[0]=='#'||line[0]=='\n')continue;
   if(sscanf(line,"%31[^,],%d,%" SCNu64 ",%" SCNu64 ",%" SCNu64 ",%" SCNu64,tag,&id,&a,&b,&c,&d)==6 && strcmp(tag,"TASK")==0){
     if(trace_config_task(eng,id,a,b,c,d))errors++;
   }else if(sscanf(line,"%31[^,],%d,%" SCNu64,tag,&id,&a)==3 && strcmp(tag,"ISR")==0){
     if(trace_config_isr(eng,id,a))errors++;
   }else{fprintf(stderr,"invalid config line %d\n",line_n);errors++;}
 }
 fclose(f);return errors?-1:0;
}
static int read_events(trace_engine *eng,const char *path){
 FILE *f=fopen(path,"r");char line[512];int line_n=0,errors=0;
 if(!f){perror(path);return -1;}
 while(fgets(line,sizeof(line),f)){
   trace_event ev;char tag[32];int id=0,aux=0;
   int n;
   ++line_n;if(line[0]=='#'||line[0]=='\n')continue;
   n=sscanf(line,"%" SCNu64 ",%31[^,],%d,%d",&ev.ts_us,tag,&id,&aux);
   if(n>=2){size_t len=strlen(tag);while(len && isspace((unsigned char)tag[len-1]))tag[--len]=0;}
   if(n<2||trace_parse_type(tag,&ev.type)!=0){fprintf(stderr,"invalid event line %d\n",line_n);errors++;continue;}
   ev.id=n>=3?id:-1;ev.aux=n>=4?aux:0;
   if(ev.type!=EV_GAP && n<3){fprintf(stderr,"missing id on event line %d\n",line_n);errors++;continue;}
   if(trace_feed(eng,&ev)!=0)errors++;
 }
 fclose(f);return errors?-1:0;
}
int main(int argc,char **argv){
 trace_engine e;int status;
 if(argc!=3){fprintf(stderr,"Usage: %s <config.csv> <decoded-events.csv>\n",argv[0]);return 2;}
 trace_engine_init(&e,stdout);
 if(read_config(&e,argv[1])!=0)return 2;
 status=read_events(&e,argv[2]);trace_finish(&e);
 return status==0?0:1;
}
