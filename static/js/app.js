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
        modal.classList.add('open');
      }
    });
  });
}
bindModalOpeners();
document.querySelectorAll('[data-modal-close]').forEach((button)=>{button.addEventListener('click',()=>button.closest('.modal').classList.remove('open'))});
document.querySelectorAll('.modal').forEach((modal)=>{modal.addEventListener('click',(event)=>{if(event.target===modal)modal.classList.remove('open')})});

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
const backgroundFocusButton=document.getElementById('backgroundFocusButton');
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
function completeFocusInBackground(){
  clearFocusState();
  fetch('/focus/complete',{method:'POST',credentials:'same-origin'}).then(()=>{launchConfetti(25,'Фокус-сессия завершена! +25 очков опыта')}).catch(()=>{});
}
function checkGlobalFocusTimer(){
  const state=getFocusState();
  if(!state || !state.started || state.completed)return;
  if(calculateSecondsFromState(state)<=0){completeFocusInBackground();}
}
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
if(backgroundFocusButton){backgroundFocusButton.addEventListener('click',()=>{window.location.href='/dashboard'})}
if(leaveFocusButton){leaveFocusButton.addEventListener('click',()=>{stopTimerOnly();clearFocusState();window.location.href='/dashboard'})}
renderTimer();
checkGlobalFocusTimer();
setInterval(()=>{if(timerElement){renderTimer()}else{checkGlobalFocusTimer()}},1000);

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
const earned=document.body.dataset.confettiEarned;
if(earned){launchConfetti(earned)}
