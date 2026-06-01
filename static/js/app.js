function calculateAutoPriority(importance, urgency){
  if(urgency==='urgent' && importance==='high') return {value:'high', label:'Высокий'};
  if(urgency==='urgent' || importance==='high') return {value:'medium', label:'Средний'};
  return {value:'low', label:'Низкий'};
}
function updateAutoPriority(scope){
  const root=scope||document;
  root.querySelectorAll('form').forEach((form)=>{
    const importance=form.querySelector('[data-task-importance]');
    const urgency=form.querySelector('[data-task-urgency]');
    const target=form.querySelector('[data-auto-priority]');
    if(!importance || !urgency || !target) return;
    const result=calculateAutoPriority(importance.value,urgency.value);
    target.textContent=result.label;
    target.classList.remove('low','medium','high');
    target.classList.add(result.value);
  });
}
function bindModalOpeners(){
  document.querySelectorAll('[data-modal-open]').forEach((button)=>{
    if(button.dataset.boundModal)return;
    button.dataset.boundModal='1';
    button.addEventListener('click',(event)=>{
      event.preventDefault();
      event.stopPropagation();
      const modal=document.getElementById(button.dataset.modalOpen);
      if(modal){
        const importance=button.dataset.presetImportance;
        const urgency=button.dataset.presetUrgency;
        if(importance){const field=modal.querySelector('[data-task-importance]'); if(field)field.value=importance;}
        if(urgency){const field=modal.querySelector('[data-task-urgency]'); if(field)field.value=urgency;}
        updateAutoPriority(modal);
        modal.classList.add('open');
      }
    });
  });
}
bindModalOpeners();
document.querySelectorAll('[data-modal-close]').forEach((button)=>{button.addEventListener('click',()=>button.closest('.modal').classList.remove('open'))});
document.querySelectorAll('.modal').forEach((modal)=>{modal.addEventListener('click',(event)=>{if(event.target===modal)modal.classList.remove('open')})});
document.addEventListener('change',(event)=>{if(event.target.matches('[data-task-importance],[data-task-urgency]')) updateAutoPriority(event.target.closest('.modal')||document)});
updateAutoPriority(document);

document.querySelectorAll('[data-subtask-editor]').forEach((editor)=>{
  editor.addEventListener('click',(event)=>{
    const addButton=event.target.closest('[data-add-subtask]');
    const removeButton=event.target.closest('[data-remove-subtask]');
    if(addButton){
      const row=document.createElement('div');
      row.className='subtask-input-row';
      row.innerHTML='<input name="subtask_items" placeholder="Новый подпункт"><button class="icon-btn" type="button" data-remove-subtask>×</button>';
      editor.appendChild(row);
      row.querySelector('input').focus();
    }
    if(removeButton){
      const row=removeButton.closest('.subtask-input-row');
      if(row)row.remove();
    }
  });
});

const timerElement=document.getElementById('timer');
const timerShell=document.getElementById('timerShell');
const timerMainButton=document.getElementById('timerMainButton');
const earlyFinishButton=document.getElementById('earlyFinishButton');
const earlyFinishModal=document.getElementById('earlyFinishModal');
const stayFocusButton=document.getElementById('stayFocusButton');
const leaveFocusButton=document.getElementById('leaveFocusButton');
const focusBackLink=document.getElementById('focusBackLink');
const completeFocusForm=document.getElementById('completeFocusForm');
const focusTaskSelect=document.getElementById('focusTask');
const focusTaskIdInput=document.getElementById('focusTaskIdInput');
const completeTaskInput=document.getElementById('completeTaskInput');
const focusTaskCompleteModal=document.getElementById('focusTaskCompleteModal');
const focusCompletedTaskText=document.getElementById('focusCompletedTaskText');
const completeSelectedTaskButton=document.getElementById('completeSelectedTaskButton');
const keepTaskInProgressButton=document.getElementById('keepTaskInProgressButton');
let pendingFocusHref=null;
const FOCUS_KEY='focusPlanTimerState';
const totalSecondsDefault=25*60;
let totalSeconds=totalSecondsDefault;
let secondsLeft=totalSecondsDefault;
let timerId=null;
let timerStarted=false;
let isPaused=false;

function getFocusState(){
  try{return JSON.parse(localStorage.getItem(FOCUS_KEY)||'null')}catch(e){return null}
}
function saveFocusState(state){localStorage.setItem(FOCUS_KEY,JSON.stringify(state))}
function clearFocusState(){localStorage.removeItem(FOCUS_KEY)}
function calculateSecondsFromState(state){
  if(!state)return totalSecondsDefault;
  if(state.running){return Math.max(0,Math.ceil((state.endAt-Date.now())/1000));}
  return Math.max(0,parseInt(state.secondsLeft||totalSecondsDefault,10));
}
function submitFocusCompletion(completeTask){
  if(focusTaskIdInput && focusTaskSelect){
    focusTaskIdInput.value=focusTaskSelect.value||'';
  }
  if(completeTaskInput){
    completeTaskInput.value=completeTask?'1':'0';
  }
  if(completeFocusForm){
    completeFocusForm.submit();
  }
}
function completeFocusInBackground(){ clearFocusState(); }
function renderTimer(){
  const state=getFocusState();
  if(state){
    totalSeconds=parseInt(state.totalSeconds||totalSecondsDefault,10);
    secondsLeft=calculateSecondsFromState(state);
    timerStarted=Boolean(state.started);
    isPaused=Boolean(state.started && !state.running && secondsLeft>0);
  }
  if(timerElement){
    const minutes=String(Math.floor(secondsLeft/60)).padStart(2,'0');
    const seconds=String(secondsLeft%60).padStart(2,'0');
    timerElement.textContent=`${minutes}:${seconds}`;
  }
  if(timerShell){
    const passed=totalSeconds-secondsLeft;
    const deg=Math.round((passed/totalSeconds)*360);
    timerShell.style.setProperty('--timer-progress',deg+'deg');
  }
  if(timerMainButton){
    if(!timerStarted){timerMainButton.textContent='Старт'}
    else if(isPaused){timerMainButton.textContent='Продолжить'}
    else{timerMainButton.textContent='Пауза'}
  }
  if(earlyFinishButton){
    if(timerStarted && secondsLeft>0) earlyFinishButton.classList.remove('hidden');
    else earlyFinishButton.classList.add('hidden');
  }
}
function stopTimerOnly(){if(timerId)clearInterval(timerId);timerId=null}
function startTimer(){
  stopTimerOnly();
  const state={started:true,running:true,totalSeconds:totalSeconds,secondsLeft:secondsLeft,endAt:Date.now()+secondsLeft*1000};
  saveFocusState(state);
  timerStarted=true;isPaused=false;
  renderTimer();
  timerId=setInterval(()=>{
    renderTimer();
    if(secondsLeft<=0){
      stopTimerOnly();
      clearFocusState();
      if(focusTaskSelect && focusTaskSelect.value){
        const selectedOption=focusTaskSelect.options[focusTaskSelect.selectedIndex];
        const taskTitle=selectedOption ? selectedOption.textContent.trim() : '';
        if(focusCompletedTaskText){
          focusCompletedTaskText.textContent=taskTitle ? `Вы работали над задачей «${taskTitle}». Отметить её выполненной?` : 'Отметить выбранную задачу выполненной?';
        }
        if(focusTaskCompleteModal){
          focusTaskCompleteModal.classList.add('open');
        }else{
          submitFocusCompletion(false);
        }
      }else{
        submitFocusCompletion(false);
      }
    }
  },1000);
}
function pauseTimer(){
  stopTimerOnly();
  const state=getFocusState()||{};
  secondsLeft=calculateSecondsFromState(state);
  saveFocusState({started:true,running:false,totalSeconds:totalSeconds,secondsLeft:secondsLeft,endAt:null});
  isPaused=true;
  renderTimer();
}
function hasActiveFocusSession(){
  const state = getFocusState();

  return Boolean(
    state &&
    state.started &&
    state.running &&
    calculateSecondsFromState(state) > 0
  );
}
function askEarlyFinish(event, href=null){
  if(hasActiveFocusSession()){
    if(event)event.preventDefault();
    pendingFocusHref=href;
    if(earlyFinishModal)earlyFinishModal.classList.add('open');
  }
}
function bindFocusNavigationWarning(){
  if(!timerElement)return;
  const links=[...document.querySelectorAll('.sidebar a, #focusBackLink')];
  links.forEach((link)=>{
    if(link.dataset.focusWarningBound)return;
    link.dataset.focusWarningBound='1';
    link.addEventListener('click',(event)=>{
      const href=link.getAttribute('href');
      if(!href || href.startsWith('#'))return;
      const currentUrl=window.location.pathname+window.location.search;
      if(href===currentUrl || href===window.location.pathname)return;
      askEarlyFinish(event, href);
    });
  });
}
if(timerMainButton){
  const state=getFocusState();
  if(state && state.started && calculateSecondsFromState(state)>0){
    if(state.running) startTimer(); else renderTimer();
  }
  timerMainButton.addEventListener('click',()=>{
    const state=getFocusState();
    if(!state || !state.started || calculateSecondsFromState(state)<=0){
      totalSeconds=totalSecondsDefault; secondsLeft=totalSecondsDefault; startTimer(); return;
    }
    if(state.running){pauseTimer(); return;}
    secondsLeft=calculateSecondsFromState(state); startTimer();
  });
}
if(earlyFinishButton){earlyFinishButton.addEventListener('click',(event)=>askEarlyFinish(event))}
bindFocusNavigationWarning();
if(stayFocusButton){stayFocusButton.addEventListener('click',()=>{if(earlyFinishModal)earlyFinishModal.classList.remove('open')})}
if(leaveFocusButton){leaveFocusButton.addEventListener('click',()=>{stopTimerOnly();clearFocusState();window.location.href=pendingFocusHref||'/dashboard'})}
if(completeSelectedTaskButton){completeSelectedTaskButton.addEventListener('click',()=>submitFocusCompletion(true))}
if(keepTaskInProgressButton){keepTaskInProgressButton.addEventListener('click',()=>submitFocusCompletion(false))}
renderTimer();
setInterval(()=>{if(timerElement){renderTimer()}},1000);

function showToast(message, type='info', duration=4600){
  if(!message)return;

  const toast=document.createElement('div');
  toast.className=`toast ${type}-toast`;

  const icon=document.createElement('span');
  icon.className='toast-icon';
  icon.textContent=type==='reminder' ? '🔔' : (type==='achievement' ? '⭐' : '✦');

  const text=document.createElement('span');
  text.className='toast-text';
  text.textContent=message;

  toast.appendChild(icon);
  toast.appendChild(text);
  document.body.appendChild(toast);

  setTimeout(()=>toast.classList.add('show'), 20);
  setTimeout(()=>{
    toast.classList.remove('show');
    setTimeout(()=>toast.remove(), 260);
  }, duration);
}

function launchConfetti(earned, message){
  const layer=document.getElementById('confettiLayer');
  if(layer){
    const colors=['#7c5cff','#22a06b','#ec72a7','#ffb020','#3b82f6','#ff5b5b'];
    for(let i=0;i<90;i++){
      const piece=document.createElement('div');
      piece.className='confetti-piece';
      piece.style.left=Math.random()*100+'vw';
      piece.style.backgroundColor=colors[Math.floor(Math.random()*colors.length)];
      piece.style.animationDelay=Math.random()*0.3+'s';
      piece.style.transform=`rotate(${Math.random()*360}deg)`;
      layer.appendChild(piece);
      setTimeout(()=>piece.remove(),2100);
    }
  }

  showToast(message||`Задача выполнена! +${earned} XP`, 'achievement', 5200);
}

function launchToast(message){
  const type=String(message||'').startsWith('Достижение') ? 'achievement' : 'info';
  showToast(message, type, 4800);
}

function parseTaskDateTime(task){
  if(!task || !task.date)return null;
  const dateParts=String(task.date).split('-').map(Number);
  if(dateParts.length!==3 || dateParts.some(Number.isNaN))return null;

  const timeValue=task.time || '09:00';
  const timeParts=String(timeValue).split(':').map(Number);
  const hours=Number.isFinite(timeParts[0]) ? timeParts[0] : 9;
  const minutes=Number.isFinite(timeParts[1]) ? timeParts[1] : 0;

  return new Date(dateParts[0], dateParts[1]-1, dateParts[2], hours, minutes, 0, 0);
}

function estimateToMilliseconds(task){
  const value=parseFloat(String(task.estimate_value||'').replace(',', '.'));
  if(!Number.isFinite(value) || value<=0)return 0;

  const unit=task.estimate_unit || 'hours';
  if(unit==='minutes')return value*60*1000;
  if(unit==='days')return value*24*60*60*1000;
  return value*60*60*1000;
}

function alreadyShownReminder(key){
  try{return localStorage.getItem(key)==='1'}catch(e){return false}
}

function markReminderShown(key){
  try{localStorage.setItem(key, '1')}catch(e){}
}

function reminderKey(task, stage){
  return `focusplan-reminder-${task.id}-${task.date}-${task.time||'day'}-${stage}`;
}

function maybeShowReminder(task, stage, message, delayIndex=0){
  const key=reminderKey(task, stage);
  if(alreadyShownReminder(key))return;

  markReminderShown(key);
  setTimeout(()=>showToast(message, 'reminder', 6200), 600 + delayIndex*700);
}

function checkTaskReminders(){
  if(document.body.dataset.notificationsEnabled==='0')return;

  const dataNode=document.getElementById('reminderTasksData');
  if(!dataNode)return;

  let tasks=[];
  try{tasks=JSON.parse(dataNode.textContent||'[]')}catch(e){tasks=[]}
  if(!Array.isArray(tasks) || !tasks.length)return;

  const now=new Date();
  const todayString=[
    now.getFullYear(),
    String(now.getMonth()+1).padStart(2,'0'),
    String(now.getDate()).padStart(2,'0')
  ].join('-');

  const dayTasks=[];
  let notificationIndex=0;

  tasks.forEach((task)=>{
    if(!task || !task.date)return;

    const title=task.title || 'Задача';

    if(!task.time){
      if(task.date===todayString){
        dayTasks.push(task);
      }
      return;
    }

    const deadline=parseTaskDateTime(task);
    if(!deadline)return;

    const diff=deadline.getTime()-now.getTime();
    const estimateMs=estimateToMilliseconds(task);

    if(estimateMs>0){
      const startAt=deadline.getTime()-estimateMs;
      if(now.getTime()>=startAt && now.getTime()<deadline.getTime()){
        maybeShowReminder(task, 'start', `Пора начать задачу: «${title}»`, notificationIndex++);
      }
    }

    if(diff>0 && diff<=15*60*1000){
      maybeShowReminder(task, 'soon', `Скоро время задачи: «${title}»`, notificationIndex++);
    }

    if(diff<0){
      maybeShowReminder(task, 'unfinished', `У вас есть незавершённая задача: «${title}»`, notificationIndex++);
    }
  });

  if(dayTasks.length){
    const key=`focusplan-reminder-day-${todayString}-${dayTasks.map((task)=>task.id).join('-')}`;
    if(!alreadyShownReminder(key)){
      markReminderShown(key);
      const message=dayTasks.length===1
        ? `Сегодня у вас запланирована задача: «${dayTasks[0].title || 'Задача'}»`
        : `Сегодня у вас запланировано ${dayTasks.length} задач без точного времени`;
      setTimeout(()=>showToast(message, 'reminder', 6200), 600 + notificationIndex*700);
    }
  }
}

const earned=document.body.dataset.confettiEarned;
const confettiMessage=document.body.dataset.confettiMessage;
if(earned){launchConfetti(earned, confettiMessage || undefined)}
try{
  const toastData=document.getElementById('toastData');
  const messages=toastData ? JSON.parse(toastData.textContent||'[]') : [];
  messages.forEach((message,index)=>setTimeout(()=>launchToast(message), 250+index*550));
}catch(e){}

checkTaskReminders();
setInterval(checkTaskReminders, 60*1000);


function openTaskModalWithDateTime(dateValue, timeValue){
  const modal=document.getElementById('taskModal');
  if(!modal)return;

  const dateInput=modal.querySelector('input[name="date"]');
  const timeInput=modal.querySelector('input[name="time"]');

  if(dateInput && dateValue) dateInput.value=dateValue;
  if(timeInput) timeInput.value=timeValue || '';

  updateAutoPriority(modal);
  modal.classList.add('open');

  const titleInput=modal.querySelector('input[name="title"]');
  if(titleInput) setTimeout(()=>titleInput.focus(), 80);
}

function bindCalendarInteractions(){
  const taskViewModal=document.getElementById('calendarTaskViewModal');
  const calendarTaskEditButton=document.getElementById('calendarTaskEditButton');

  if(calendarTaskEditButton && !calendarTaskEditButton.dataset.editButtonBound){
    calendarTaskEditButton.dataset.editButtonBound='1';
    calendarTaskEditButton.addEventListener('click',()=>{
      if(!taskViewModal)return;
      const editModalId=taskViewModal.dataset.editModal;
      taskViewModal.classList.remove('open');
      if(!editModalId)return;
      const editModal=document.getElementById(editModalId);
      if(editModal){
        updateAutoPriority(editModal);
        editModal.classList.add('open');
      }
    });
  }

  document.querySelectorAll('[data-calendar-task]').forEach((taskElement)=>{
    if(taskElement.dataset.calendarTaskBound)return;
    taskElement.dataset.calendarTaskBound='1';

    taskElement.addEventListener('click',(event)=>{
      event.preventDefault();
      event.stopPropagation();

      if(!taskViewModal)return;

      const setText=(id,value)=>{
        const element=document.getElementById(id);
        if(element) element.textContent=value || '—';
      };

      setText('calendarTaskTitle', taskElement.dataset.taskTitle);
      setText('calendarTaskDate', taskElement.dataset.taskDate);
      setText('calendarTaskTime', taskElement.dataset.taskTime);
      setText('calendarTaskFolder', taskElement.dataset.taskFolder);
      setText('calendarTaskPriority', taskElement.dataset.taskPriority);
      setText('calendarTaskImportance', taskElement.dataset.taskImportance);
      setText('calendarTaskUrgency', taskElement.dataset.taskUrgency);
      setText('calendarTaskXp', taskElement.dataset.taskXp);

      const description=document.getElementById('calendarTaskDescription');
      if(description){
        const text=taskElement.dataset.taskDescription || '';
        description.textContent=text || 'Описание не указано';
      }

      taskViewModal.dataset.editModal=taskElement.dataset.taskEditModal || '';
      taskViewModal.classList.add('open');
    });
  });

  document.querySelectorAll('[data-calendar-date]').forEach((cell)=>{
    if(cell.dataset.calendarCellBound)return;
    cell.dataset.calendarCellBound='1';

    cell.addEventListener('click',(event)=>{
      if(event.target.closest('[data-calendar-task]'))return;
      openTaskModalWithDateTime(cell.dataset.calendarDate, cell.dataset.calendarTime || '');
    });
  });
}

bindCalendarInteractions();

function bindMatrixInteractions(){
  const taskViewModal = document.getElementById('calendarTaskViewModal');

  document.querySelectorAll('[data-matrix-task]').forEach((taskElement)=>{
    if(taskElement.dataset.matrixTaskBound) return;
    taskElement.dataset.matrixTaskBound = '1';

    taskElement.addEventListener('click', (event)=>{
      event.preventDefault();
      event.stopPropagation();

      if(!taskViewModal) return;

      const setText = (id, value)=>{
        const element = document.getElementById(id);
        if(element) element.textContent = value || '—';
      };

      setText('calendarTaskTitle', taskElement.dataset.taskTitle);
      setText('calendarTaskDate', taskElement.dataset.taskDate);
      setText('calendarTaskTime', taskElement.dataset.taskTime);
      setText('calendarTaskFolder', taskElement.dataset.taskFolder);
      setText('calendarTaskPriority', taskElement.dataset.taskPriority);
      setText('calendarTaskImportance', taskElement.dataset.taskImportance);
      setText('calendarTaskUrgency', taskElement.dataset.taskUrgency);
      setText('calendarTaskXp', taskElement.dataset.taskXp);

      const description = document.getElementById('calendarTaskDescription');
      if(description){
        const text = taskElement.dataset.taskDescription || '';
        description.textContent = text || 'Описание не указано';
      }

      const editButton = document.getElementById('calendarTaskEditButton');

      if(editButton){
        editButton.onclick = () => {
          taskViewModal.classList.remove('open');

          const editModalId = taskElement.dataset.taskEditModal;
          const editModal = document.getElementById(editModalId);

          if(editModal){
            editModal.classList.add('open');
          }
        };
      }

      taskViewModal.classList.add('open');
    });
  });
}

bindMatrixInteractions();