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
      if(completeFocusForm)completeFocusForm.submit();
      else completeFocusInBackground();
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
function askEarlyFinish(event){
  const state=getFocusState();
  if(state && state.started && calculateSecondsFromState(state)>0){
    event.preventDefault();
    if(earlyFinishModal)earlyFinishModal.classList.add('open');
  }
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
if(focusBackLink){focusBackLink.addEventListener('click',(event)=>askEarlyFinish(event))}
if(stayFocusButton){stayFocusButton.addEventListener('click',()=>{if(earlyFinishModal)earlyFinishModal.classList.remove('open')})}
if(leaveFocusButton){leaveFocusButton.addEventListener('click',()=>{stopTimerOnly();clearFocusState();window.location.href='/dashboard'})}
renderTimer();
setInterval(()=>{if(timerElement){renderTimer()}},1000);

function launchConfetti(earned, message){
  const layer=document.getElementById('confettiLayer');
  if(!layer)return;
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
  const toast=document.createElement('div');
  toast.className='toast';
  toast.textContent=message||`Задача выполнена! +${earned} очков опыта`;
  document.body.appendChild(toast);
  setTimeout(()=>toast.remove(),2600);
}

function launchToast(message){
  const toast=document.createElement('div');
  toast.className='toast info-toast';
  toast.textContent=message;
  document.body.appendChild(toast);
  setTimeout(()=>toast.remove(),3200);
}

const earned=document.body.dataset.confettiEarned;
const confettiMessage=document.body.dataset.confettiMessage;
if(earned){launchConfetti(earned, confettiMessage || undefined)}
try{
  const toastData=document.getElementById('toastData');
  const messages=toastData ? JSON.parse(toastData.textContent||'[]') : [];
  messages.forEach((message,index)=>setTimeout(()=>launchToast(message), 250+index*450));
}catch(e){}
