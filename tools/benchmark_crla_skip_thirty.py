"""Opt-in skip/late-heartbeat probe: 30 synthetic students, three normal batches.

Run only in an authorized Cloud Run Job. Does not access audio or finalize grades.
Prints aggregate metrics only; exact disposable IDs and cookies stay in memory.
"""
import collections,concurrent.futures as cf,datetime as dt,http.client,json,logging,math,os,secrets,statistics,sys,threading,time,traceback,uuid
COUNT=30
def summary(rows):
 values=sorted(r['ms'] for r in rows)
 return {'count':len(rows),'mean_ms':round(statistics.mean(values),2),'p95_ms':round(values[math.ceil(.95*len(values))-1],2),'max_ms':round(max(values),2),
  'failures':sum(not r['ok'] for r in rows),'statuses':dict(collections.Counter(str(r['status']) for r in rows))}
def run():
 assert os.environ.get('CLOUD_RUN_EXECUTION') and os.environ.get('PABASA_AUTHORIZED_CRLA_SKIP_TEST')=='30'
 sys.path.insert(0,'/app/pabasa_site');os.environ.setdefault('DJANGO_SETTINGS_MODULE','pabasa_site.settings')
 import django;django.setup();logging.disable(logging.CRITICAL)
 from django.conf import settings
 from django.contrib.sessions.backends.db import SessionStore
 from django.contrib.sessions.models import Session
 from django.contrib.auth.hashers import make_password
 from django.db import connections,transaction
 from django.utils import timezone
 from pabasa_app.models import ActivityLog,Assessment,CalendarEvent,Enrollment,LiveAssessmentSession,Material,Notification,School,SchoolCalendar,Section,User
 from pabasa_app.system_clock import today
 rid=uuid.uuid4().hex[:12];host=os.environ['PABASA_SKIP_HOST'];csrf=secrets.token_hex(32)
 report={'test_id':rid,'clients':COUNT,'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
  'user_agent':'PABASA-authorized-CRLA-skip-thirty-'+rid,'aborted':False,
  'scope':'30 distinct synthetic students, three teachers/classes, three active normal batches of ten. Student cursor saves, teacher skips, late heartbeat races, idempotent teacher retry and authorization checks. No audio or official student grades.'}
 users=[];sessions=[];keys=[];clients=[];rows=[];sections=[];school=calendar=material=None
 hashed=make_password(secrets.token_urlsafe(24))
 def user(label,role):
  u=User.objects.create(custom_id='SKP-'+rid+'-'+label,role=role,first_name='Synthetic',last_name='Skip',sex='female',birth_month=1,birth_day=1,birth_year=2012,
   email=None,password_hash=hashed,school_record=school,school_calendar=calendar);users.append(u.pk);return u
 def client(u,live,student_id):
  login=SessionStore();login.update({'user_id':u.pk,'user_role':u.role,'crla_skip_probe':rid});login.set_expiry(900);login.create();keys.append(login.session_key)
  c={'key':login.session_key,'live':live.pk,'student':student_id,'conn':http.client.HTTPSConnection(host,timeout=90)};clients.append(c);return c
 def request(c,op,payload=None,expected=200,barrier=None):
  if barrier:barrier.wait(45)
  start=time.perf_counter();status=0;data={};ok=False;error=None
  path='/api/live-assessment/session/'+c['live']+'/'
  if payload is not None:path+='action/' if op in ('teacher_skip','teacher_replay','student_forbidden','foreign_teacher') else 'student-update/'
  try:
   c['conn'].request('POST' if payload is not None else 'GET',path,body=json.dumps(payload) if payload is not None else None,
    headers={'Cookie':settings.SESSION_COOKIE_NAME+'='+c['key']+'; csrftoken='+csrf,'X-CSRFToken':csrf,'Content-Type':'application/json',
     'Origin':'https://'+host,'Referer':'https://'+host+'/','User-Agent':report['user_agent']})
   response=c['conn'].getresponse();status=response.status;data=json.loads(response.read());ok=status==expected and (expected!=200 or data.get('success') is True)
   if op in ('late_heartbeat','after_skip'):
    ok=ok and data.get('session',{}).get('student_states',{}).get(str(c['student']),{}).get('status')=='skipped'
   if op=='teacher_replay':
    ok=ok and data.get('session',{}).get('overall_completed')==10 and data.get('session',{}).get('all_selected_students_completed') is False
   if op=='comprehension_saved':
    recovery=data.get('session',{}).get('student_states',{}).get(str(c['student']),{}).get('recovery_state',{})
    ok=ok and recovery.get('stage')=='story_comprehension' and recovery.get('crla_question_index')==2
  except Exception as exc:error=type(exc).__name__
  row={'status':status,'ok':ok,'ms':1000*(time.perf_counter()-start),'operation':op,'error_type':error};rows.append(row)
  return row
 def wave(pool,members,op,payload=None,expected=200):
  barrier=threading.Barrier(len(members))
  result=list(pool.map(lambda c:request(c,op,payload(c) if callable(payload) else payload,expected,barrier),members))
  stats={'operation':op,**summary(result)};print('PABASA_SKIP_WAVE '+json.dumps(stats),flush=True)
  assert all(r['ok'] for r in result),'Probe wave failed; do not hide errors with retries'
 try:
  with transaction.atomic():
   school=School.objects.create(name='Synthetic skip '+rid,code='SKP'+rid)
   calendar=SchoolCalendar.objects.create(school_year='SKP-'+rid,is_active=False,current_term=1)
   day=today()
   for kind,first,last in [('school_opening',day-dt.timedelta(days=2),day-dt.timedelta(days=2)),('pre_assessment',day-dt.timedelta(days=1),day+dt.timedelta(days=1)),('school_closing',day+dt.timedelta(days=20),day+dt.timedelta(days=20))]:
    CalendarEvent.objects.create(school_calendar=calendar,school=school,scope=CalendarEvent.SCOPE_SCHOOL,term=1,title='Synthetic '+kind,event_type=kind,start_date=first,end_date=last)
   source=Material.objects.filter(system_assessment_key='bosy_crla_pretest').first();assert source
   students=[];teachers=[]
   for group in range(3):
    teacher=user('T'+str(group),'teacher')
    section=Section.objects.create(school=school,school_calendar=calendar,teacher=teacher,class_code='SKP'+rid+str(group),class_name='Synthetic skip class',subject='Reading',assessment_week_enabled=True);sections.append(section.pk)
    if material is None:
     root=Assessment.objects.create(teacher=teacher,title='Synthetic skip '+rid,code='SKPROOT'+rid,assessment_type=source.item_type,status='published',is_system_owned=True,
      system_assessment_key='skip_'+rid,system_assessment_period='bosy',system_assessment_phase='pretest',official_term=1)
     material=Material.objects.create(assessment=root,teacher=teacher,title='Synthetic skip '+rid,code='SKPMAT'+rid,system_assessment_key='skip_'+rid,
      is_system_owned=True,is_official_reading=True,assessment_kind='crla',assessment_set='crla',system_assessment_period='bosy',system_assessment_phase='pretest',official_term=1,
      item_type=source.item_type,language=source.language,content_json=source.content_json,content_text=source.content_text,type='assessment',status='published')
    material.assigned_sections.add(section)
    members=[]
    for i in range(10):
     student=user(str(group*10+i),'student');section.add_student(student);members.append(student)
    live=LiveAssessmentSession.objects.create(id='skip-'+rid+'-'+str(group),teacher=teacher,section=section,material=material,status='started',start_at=timezone.now(),
     student_ids=[u.pk for u in members],student_count=10,batch_size=10,current_batch=1,total_batches=1,batch_assignments={str(u.pk):1 for u in members},
     student_states={str(u.pk):{'status':'reading','progress':0,'connection_status':'connected'} for u in members});sessions.append(live.pk)
    for student in members:
     students.append(client(student,live,student.pk));teachers.append(client(teacher,live,student.pk))
  report['enrolled_students']=Enrollment.objects.filter(student_id__in=users,status='active',is_active=True).count();assert report['enrolled_students']==COUNT
  connections.close_all();report['http_started_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
  with cf.ThreadPoolExecutor(max_workers=COUNT) as pool:
   wave(pool,students,'before_skip')
   for cursor in (1,2,3):
    wave(pool,students,'student_skip_cursor',{'status':'reading','recovery_state':{'stage':'words','task1_score':0,'crla_question_index':cursor}})
   wave(pool,students,'comprehension_cursor',{'status':'reading','recovery_state':{'stage':'story_comprehension',
    'crla_question_index':2,'crla_answers':['','',''],'crla_results':[None,None,None]}})
   wave(pool,students,'comprehension_saved')
   # Three teacher controls each skip their own ten students while all thirty
   # student connections continue heartbeating; this uses normal batch sizes.
   def skip_batch(group):
    for c in teachers[group*10:(group+1)*10]:
     result=request(c,'teacher_skip',{'action':'skip_student','student_id':c['student']});assert result['ok']
   with cf.ThreadPoolExecutor(max_workers=3) as controls:
    pending=[controls.submit(skip_batch,g) for g in range(3)]
    wave(pool,students,'racing_heartbeat',{'status':'reading','progress':.2,'recovery_state':{'stage':'story_comprehension','crla_question_index':2}})
    for task in pending:task.result()
   wave(pool,students,'late_heartbeat',{'status':'reading','progress':.9,'recovery_state':{'stage':'sentences','crla_question_index':9}})
   wave(pool,students,'after_skip')
   wave(pool,teachers,'teacher_replay',lambda c:{'action':'skip_student','student_id':c['student']})
   wave(pool,students,'student_forbidden',lambda c:{'action':'skip_student','student_id':c['student']},expected=403)
   # An unrelated teacher cannot mutate another class's session.
   for i,c in enumerate(teachers):c['original_live']=c['live'];c['live']=sessions[(i//10+1)%3]
   wave(pool,teachers,'foreign_teacher',lambda c:{'action':'skip_student','student_id':c['student']},expected=403)
   for c in teachers:c['live']=c.pop('original_live')
  report['http_finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
  live_rows=list(LiveAssessmentSession.objects.filter(pk__in=sessions))
  states=[s for live in live_rows for s in live.student_states.values()]
  report['skipped_students']=sum(s.get('status')=='skipped' for s in states)
  report['retained_skip_cursors']=sum(s.get('recovery_state',{}).get('crla_question_index')==2 for s in states)
  report['official_student_results']=Assessment.objects.filter(student_id__in=users,attempt_status='completed').count()
  report['student_logins_preserved']=Session.objects.filter(session_key__in=[c['key'] for c in students]).count()
  assert report['skipped_students']==report['retained_skip_cursors']==report['student_logins_preserved']==COUNT
  assert report['official_student_results']==0
 except Exception as exc:
  report['aborted']=True;report['error_type']=type(exc).__name__;report['error_locations']=[{'file':os.path.basename(f.filename),'line':f.lineno} for f in traceback.extract_tb(exc.__traceback__)]
 finally:
  for c in clients:c['conn'].close()
  connections.close_all();Session.objects.filter(session_key__in=keys).delete()
  Notification.objects.filter(created_by_id__in=users).delete();ActivityLog.objects.filter(actor_id__in=users).delete()
  User.objects.filter(pk__in=users).delete();Section.objects.filter(pk__in=sections).delete()
  if calendar:SchoolCalendar.objects.filter(pk=calendar.pk).delete()
  if school:School.objects.filter(pk=school.pk).delete()
  report['remaining_users']=User.objects.filter(pk__in=users).count();report['remaining_sessions']=Session.objects.filter(session_key__in=keys).count()
  report['remaining_live_sessions']=LiveAssessmentSession.objects.filter(pk__in=sessions).count()
  report['operations']={name:summary([r for r in rows if r['operation']==name]) for name in sorted({r['operation'] for r in rows})}
  report['failures']=sum(not r['ok'] for r in rows);report['total_requests']=len(rows);report['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
  print('PABASA_SKIP_THIRTY '+json.dumps(report),flush=True)
 if report['aborted']:raise SystemExit(1)
if __name__=='__main__':run()
