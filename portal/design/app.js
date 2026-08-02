(function(){
  "use strict";
  var nav=document.getElementById("nav");
  var toggle=document.getElementById("toggle");
  if(!nav||!toggle){return;}
  toggle.addEventListener("click",function(){
    var open=nav.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded",open?"true":"false");
  });
  document.addEventListener("click",function(event){
    var profile=document.querySelector(".profile-menu[open]");
    if(profile&&!profile.contains(event.target)){profile.removeAttribute("open");}
    if(window.innerWidth>860||nav.contains(event.target)||toggle.contains(event.target)){return;}
    nav.classList.remove("is-open");
    toggle.setAttribute("aria-expanded","false");
  });
  function groupDatabaseCards(){
    var source=document.querySelector('.js-owner-resource-source[data-resource-kind="banco"]');
    if(!source){return;}
    var cards=Array.prototype.slice.call(source.querySelectorAll('.db96-card[data-resource-owner]'));
    if(!cards.length){return;}
    var current=source.getAttribute('data-current-user')||'';
    var groups=new Map();
    cards.forEach(function(card){
      var owner=card.getAttribute('data-resource-owner')||'';
      if(!groups.has(owner)){groups.set(owner,[]);}
      groups.get(owner).push(card);
    });
    var ordered=Array.from(groups.entries()).sort(function(a,b){
      if(a[0]===current){return -1;}
      if(b[0]===current){return 1;}
      return (a[0]||'~').localeCompare(b[0]||'~','pt-BR');
    });
    var container=document.createElement('div');
    container.className='owner-resource-groups';
    ordered.forEach(function(entry){
      var owner=entry[0],items=entry[1];
      var details=document.createElement('details');
      details.className='owner-resource-group';
      if(owner===current){details.open=true;}
      var summary=document.createElement('summary');
      var label=document.createElement('span');
      label.textContent=owner?(owner+(owner===current?' · você':'')):'Sem usuário vinculado';
      var count=document.createElement('span');
      count.className='owner-resource-count';
      count.textContent=items.length+' '+(items.length===1?'banco':'bancos');
      summary.appendChild(label);summary.appendChild(count);
      var list=document.createElement('div');list.className='owner-resource-items';
      items.forEach(function(card){list.appendChild(card);});
      details.appendChild(summary);details.appendChild(list);container.appendChild(details);
    });
    source.insertBefore(container,source.firstChild);
  }
  groupDatabaseCards();
  document.querySelectorAll('form[action$="/action/publication"]').forEach(function(form){
    form.addEventListener('submit',function(){
      var button=form.querySelector('button[type="submit"],button:not([type])');
      if(button){button.disabled=true;button.textContent='Enviando…';}
    });
  });
  document.addEventListener("keydown",function(event){
    if(event.key==="Escape"){
      nav.classList.remove("is-open");
      toggle.setAttribute("aria-expanded","false");
    }
  });
}());
