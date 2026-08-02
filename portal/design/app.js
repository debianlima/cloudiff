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
  document.addEventListener("keydown",function(event){
    if(event.key==="Escape"){
      nav.classList.remove("is-open");
      toggle.setAttribute("aria-expanded","false");
    }
  });
}());
