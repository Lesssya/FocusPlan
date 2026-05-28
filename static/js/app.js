document.querySelectorAll('[data-modal-open]').forEach((button)=>{button.addEventListener('click',()=>{const modal=document.getElementById(button.dataset.modalOpen);if(modal)modal.classList.add('open')})});
document.querySelectorAll('[data-modal-close]').forEach((button)=>{button.addEventListener('click',()=>button.closest('.modal').classList.remove('open'))});
document.querySelectorAll('.modal').forEach((modal)=>{modal.addEventListener('click',(event)=>{if(event.target===modal)modal.classList.remove('open')})});

const timerElement=document.getElementById('timer');
const timerMainButton=document.getElementById('timerMainButton');
const earlyFinishButton=document.getElementById('earlyFinishButton');
const earlyFinishModal=document.getElementById('earlyFinishModal');
const stayFocusButton=document.getElementById('stayFocusButton');
const leaveFocusButton=document.getElementById('leaveFocusButton');
const completeFocusForm=document.getElementById('completeFocusForm');
let secondsLeft=25*60;let timerId=null;let timerStarted=false;let isPaused=false;
function renderTimer(){if(!timerElement)return;const minutes=String(Math.floor(secondsLeft/60)).padStart(2,'0');const seconds=String(secondsLeft%60).padStart(2,'0');timerElement.textContent=`${minutes}:${seconds}`}
function stopTimerOnly(){if(timerId)clearInterval(timerId);timerId=null}
function startTimer(){stopTimerOnly();timerStarted=true;isPaused=false;if(timerMainButton)timerMainButton.textContent='Пауза';timerId=setInterval(()=>{if(secondsLeft>0){secondsLeft-=1;renderTimer();return}stopTimerOnly();if(completeFocusForm)completeFocusForm.submit()},1000)}
if(timerMainButton){timerMainButton.addEventListener('click',()=>{if(!timerStarted||isPaused){startTimer();return}stopTimerOnly();isPaused=true;timerMainButton.textContent='Продолжить'})}
if(earlyFinishButton){earlyFinishButton.addEventListener('click',()=>{if(earlyFinishModal)earlyFinishModal.classList.add('open')})}
if(stayFocusButton){stayFocusButton.addEventListener('click',()=>{if(earlyFinishModal)earlyFinishModal.classList.remove('open')})}
if(leaveFocusButton){leaveFocusButton.addEventListener('click',()=>{stopTimerOnly();window.location.href='/dashboard'})}
renderTimer();

function launchConfetti(earned){
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
  toast.textContent=`Задача выполнена! +${earned} очков опыта`;
  document.body.appendChild(toast);
  setTimeout(()=>toast.remove(),2600);
}
const earned=document.body.dataset.confettiEarned;
if(earned){launchConfetti(earned)}
