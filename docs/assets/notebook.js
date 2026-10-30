// TripLibreLab notebook: decorative only. Lines draw as pages scroll into view; the sample-route bead follows the pointer. Honours prefers-reduced-motion.

(function(){document.documentElement.classList.add('js');var els=document.querySelectorAll('.pg,.draw');if(!('IntersectionObserver'in window)){els.forEach(function(e){e.classList.add('in')});return}
var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}})},{threshold:.15});els.forEach(function(e){io.observe(e)})})();


(function(){var b=document.getElementById('obs'),bead=document.getElementById('hbead'),host=document.querySelector('.bench');if(!b||!bead)return;
var L=b.getTotalLength(),t=0,hover=false,last=performance.now(),reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
function put(u){var p=b.getPointAtLength(u*L);bead.setAttribute('cx',p.x);bead.setAttribute('cy',p.y)}put(.35);if(reduce)return;
host.addEventListener('pointermove',function(e){var r=host.getBoundingClientRect();t=Math.max(0,Math.min(1,(e.clientX-r.left)/r.width));hover=true;host.classList.add('on');put(t)});
host.addEventListener('pointerleave',function(){hover=false});
(function f(n){if(!hover){t=(t+(n-last)/12000)%1;put(t)}last=n;requestAnimationFrame(f)})(last)})();

