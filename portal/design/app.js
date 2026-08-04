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
      label.textContent=owner===current?'Meus bancos':(owner||'Bancos sem usuário vinculado');
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

  function enableTenantPermissionAutocomplete(){
    document.querySelectorAll('.db96-permissions form[action$="/action/tenant_acl"]').forEach(function(form){
      var input=form.querySelector('input[name="subject"]');
      var type=form.querySelector('select[name="subject_type"]');
      if(!input||!type||input.dataset.adAutocomplete==='ready'){return;}
      input.dataset.adAutocomplete='ready';
      input.setAttribute('autocomplete','off');
      input.setAttribute('role','combobox');
      input.setAttribute('aria-autocomplete','list');
      input.setAttribute('aria-expanded','false');
      var results=document.createElement('div');
      results.className='tenant-acl-results';
      results.hidden=true;
      results.setAttribute('role','listbox');
      input.insertAdjacentElement('afterend',results);
      var timer=0,controller=null;
      function close(){results.hidden=true;results.innerHTML='';input.setAttribute('aria-expanded','false');}
      var verified=form.querySelector('input[name="identity_verified"]');var submit=form.querySelector('button[type="submit"]');var note=form.querySelector('.tenant-identity-note');
      function setNote(message,state){if(!note)return;note.textContent=message;note.classList.remove('is-error','is-success','is-searching');if(state)note.classList.add(state);}
      function invalidate(){if(verified)verified.value='';if(submit)submit.disabled=true;input.removeAttribute('aria-invalid');setNote('Selecione um resultado validado antes de adicionar.','');}
      function markNotFound(query){if(verified)verified.value='';if(submit)submit.disabled=true;input.setAttribute('aria-invalid','true');setNote('Usuário ou grupo "'+query+'" não encontrado no provedor de identidade.','is-error');}
      function choose(item){var principal=item.principal||item.username||item.label||'';var kind=item.type==='group'?'group':'user';input.value=principal;type.value=kind;if(verified)verified.value=kind+':'+principal;if(submit)submit.disabled=false;input.removeAttribute('aria-invalid');setNote('Identidade validada pelo provedor: '+principal+'.','is-success');close();input.focus();}
      function render(items,query){
        results.innerHTML='';
        if(!items.length){results.innerHTML='<p class="tenant-acl-empty tenant-acl-empty-error">Nenhum usuário ou grupo encontrado.</p>';results.hidden=false;input.setAttribute('aria-expanded','true');markNotFound(query);return;}
        items.slice(0,12).forEach(function(item){
          var button=document.createElement('button');button.type='button';button.className='tenant-acl-result';button.setAttribute('role','option');
          var principal=item.principal||item.username||item.label||'';
          var meta=[item.full_name,item.email||item.mail,item.type==='group'?'Grupo':'Usuário'].filter(Boolean).join(' · ');
          button.innerHTML='<strong></strong><small></small>';button.querySelector('strong').textContent=principal;button.querySelector('small').textContent=meta;
          button.addEventListener('click',function(){choose(item);});results.appendChild(button);
        });
        results.hidden=false;input.setAttribute('aria-expanded','true');
      }
      input.addEventListener('input',function(){
        invalidate();window.clearTimeout(timer);var q=input.value.trim();if(q.length<2){close();return;}
        timer=window.setTimeout(async function(){
          if(controller){controller.abort();}controller=new AbortController();
          results.hidden=false;results.innerHTML='<p class="tenant-acl-empty">Pesquisando no provedor de identidade…</p>';input.setAttribute('aria-expanded','true');setNote('Pesquisando usuário ou grupo…','is-searching');
          try{
            var url='/cloudiff/portal/api/admin-ad-search?q='+encodeURIComponent(q)+'&type='+encodeURIComponent(type.value||'all');
            var response=await fetch(url,{credentials:'same-origin',headers:{Accept:'application/json'},signal:controller.signal});
            var data=await response.json();if(!response.ok||!data.ok){throw new Error(data.error||'search_failed');}render(data.items||[],q);
          }catch(error){if(error.name!=='AbortError'){results.hidden=false;results.innerHTML='<p class="tenant-acl-empty tenant-acl-empty-error">Não foi possível consultar o provedor de identidade.</p>';input.setAttribute('aria-expanded','true');input.setAttribute('aria-invalid','true');setNote('Não foi possível consultar o provedor de identidade. Tente novamente.','is-error');}}
        },250);
      });
      input.addEventListener('keydown',function(event){
        var items=Array.prototype.slice.call(results.querySelectorAll('.tenant-acl-result'));if(!items.length){return;}
        var current=items.indexOf(document.activeElement);
        if(event.key==='ArrowDown'){event.preventDefault();items[Math.min(current+1,items.length-1)].focus();}
        if(event.key==='Escape'){close();input.focus();}
      });
      results.addEventListener('keydown',function(event){
        var items=Array.prototype.slice.call(results.querySelectorAll('.tenant-acl-result'));var current=items.indexOf(document.activeElement);
        if(event.key==='ArrowDown'){event.preventDefault();items[(current+1)%items.length].focus();}
        if(event.key==='ArrowUp'){event.preventDefault();if(current<=0){input.focus();}else{items[current-1].focus();}}
        if(event.key==='Escape'){close();input.focus();}
      });
      type.addEventListener('change',invalidate);form.addEventListener('submit',function(event){if(!verified||verified.value!==(type.value+':'+input.value.trim())){event.preventDefault();if(!input.value.trim()){invalidate();input.setAttribute('aria-invalid','true');setNote('Digite e selecione um usuário ou grupo retornado pelo provedor de identidade.','is-error');}else{markNotFound(input.value.trim());}input.focus();}});document.addEventListener('click',function(event){if(!form.contains(event.target)){close();}});
    });
  }
  enableTenantPermissionAutocomplete();
  document.querySelectorAll('[data-alias-edit]').forEach(function(button){
    button.addEventListener('click',function(){
      var box=button.closest('.publication-alias');
      var form=box&&box.querySelector('.publication-alias-form');
      var view=box&&box.querySelector('.publication-alias-view');
      if(form){form.hidden=false;}
      if(view){view.hidden=true;}
    });
  });
  document.querySelectorAll('[data-alias-cancel]').forEach(function(button){
    button.addEventListener('click',function(){
      var box=button.closest('.publication-alias');
      var form=box&&box.querySelector('.publication-alias-form');
      var view=box&&box.querySelector('.publication-alias-view');
      if(form){form.hidden=true;}
      if(view){view.hidden=false;}
    });
  });
  document.querySelectorAll('form[action$="/action/publication"]').forEach(function(form){
    form.addEventListener('submit',function(event){
      var button=event.submitter||form.querySelector('button[type="submit"],button:not([type])');
      if(!button){return;}
      if(button.name&&button.value){
        var operation=form.querySelector('input[data-submit-operation]');
        if(!operation){
          operation=document.createElement('input');
          operation.type='hidden';
          operation.setAttribute('data-submit-operation','true');
          form.appendChild(operation);
        }
        operation.name=button.name;
        operation.value=button.value;
      }
      button.disabled=true;
      button.textContent='Enviando…';
    });
  });
  document.addEventListener("keydown",function(event){
    if(event.key==="Escape"){
      nav.classList.remove("is-open");
      toggle.setAttribute("aria-expanded","false");
    }
  });
}());
