const toggle=document.querySelector('.menu-toggle');
const navigation=document.querySelector('#navigation');
function closeMenu(){navigation.classList.remove('open');toggle.setAttribute('aria-expanded','false');}
toggle.addEventListener('click',()=>{const open=toggle.getAttribute('aria-expanded')!=='true';toggle.setAttribute('aria-expanded',String(open));navigation.classList.toggle('open',open);});
navigation.addEventListener('click',event=>{if(event.target.closest('a'))closeMenu();});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&toggle.getAttribute('aria-expanded')==='true'){closeMenu();toggle.focus();}});
document.querySelector('.copy-email').addEventListener('click',async()=>{const status=document.querySelector('.copy-status');try{await navigator.clipboard.writeText('yamada@bku1.com');status.textContent=document.documentElement.lang==='ja'?'メールアドレスをコピーしました。':document.documentElement.lang==='zh-CN'?'邮箱地址已复制。':'Email address copied.';}catch{status.textContent=document.documentElement.lang==='ja'?'yamada@bku1.com を選択してコピーしてください。':document.documentElement.lang==='zh-CN'?'请选择并复制 yamada@bku1.com。':'Please select and copy yamada@bku1.com.';}});
