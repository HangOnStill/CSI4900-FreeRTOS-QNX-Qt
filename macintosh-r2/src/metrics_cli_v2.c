/* Standalone R2 decoded-event adapter; never claims v1 wire compatibility.
 * Usage: trace_metrics_v2 config.csv decoded_events.csv [window_us]
 */
#include "trace_metrics_v2.h"
#include <ctype.h>
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void strip(char *s) {
 size_t n=strlen(s);while(n&&isspace((unsigned char)s[n-1]))s[--n]=0;
}
static int configure(m2_engine *m,const char *path){
 FILE *f=fopen(path,"r"); char line[512]; int row=0,fail=0;
 if(!f){perror(path);return -1;}
 while(fgets(line,sizeof line,f)){
   row++;strip(line);if(line[0]=='#'||line[0]==0)continue;
   int id; uint64_t a,b,c,d; char kind[32]; char extra;
   if(sscanf(line,"TASK,%d,%" SCNu64 ",%" SCNu64 ",%" SCNu64
        ",%" SCNu64 " %c",&id,&a,&b,&c,&d,&extra)==5) {
     if(m2_config_task(m,id))fail++;
   }else if(sscanf(line,"ISR,%d,%" SCNu64 " %c",&id,&a,&extra)==2) {
     if(m2_config_isr(m,id,a))fail++;
   }else if(sscanf(line,"IDLE,%d %c",&id,&extra)==1) {
     if(m2_config_idle(m,id))fail++;
   }else {
     fprintf(stderr,"R2 invalid config line %d: %s\n",row,line);
     fail++;
   }
   (void)kind;
 }
 if(ferror(f))fail++;
 fclose(f);return fail?-1:0;
}
static int feed_events(m2_engine *m,const char *path){
 FILE *f=fopen(path,"r");char line[512];int row=0,fail=0;
 if(!f){perror(path);return -1;}
 while(fgets(line,sizeof line,f)){
   row++; if(!strchr(line,'\n')&&!feof(f)){fprintf(stderr,"R2 overlong event line %d\n",row);fail++;break;}
   strip(line);if(line[0]=='#'||line[0]==0)continue;
   m2_event ev;char name[32],extra;
   int id;int n=sscanf(line,"%" SCNu64 ",%31[^,],%d %c",&ev.ts,name,&id,&extra);
   if(n==2 && strcmp(name,"GAP")==0){id=-1;}
   else if(n!=3){fprintf(stderr,"R2 invalid event line %d: %s\n",row,line);fail++;continue;}
   if(m2_parse_type(name,&ev.type)!=0){fprintf(stderr,"R2 unknown event %s\n",name);fail++;continue;}
   ev.id=id;
   if(m2_feed(m,&ev)!=0)fail++;
 }
 if(ferror(f))fail++;
 fclose(f);return fail?-1:0;
}
int main(int argc,char **argv){
 if(argc<3||argc>4){
   fprintf(stderr,"Usage: %s config.csv decoded_events.csv [window_us]\n",argv[0]);return 2;
 }
 uint64_t win=10000;
 if(argc==4){
   errno=0;char *end=NULL;unsigned long long v=strtoull(argv[3],&end,10);
   if(errno||!end||*end||!v||v>1000000000ULL){fprintf(stderr,"invalid window size\n");return 2;}
   win=(uint64_t)v;
 }
 m2_engine m;
 m2_init(&m,stdout,win);
 if(configure(&m,argv[1])!=0)return 2;
 int feed_ok=feed_events(&m,argv[2]);
 int final=m2_finish(&m);
 return feed_ok!=0||final!=0?1:0;
}
