/* Концепт «Справочник — главная»: три входа (слова / тело / исход) и страница статьи (лесенка, ползунок, «спроси статью»).
   Данные те же, что у живого макета (справочник_данные.js); поиск и «спроси статью» ходят на сервер NNL, если он есть. */
(function(){
'use strict';
var ДАННЫЕ = window.СПРАВОЧНИК_ДАННЫЕ || {каталог:[], статьи:{}};
var СТАТЬИ = ДАННЫЕ.статьи || {};
var ПОНОМЕРУ = function(а, б){ return parseInt(а, 10) - parseInt(б, 10); };
var ИДЫ = Object.keys(СТАТЬИ).sort(ПОНОМЕРУ);

var КАТ = ['А','Б','В','Г','Д'];
var КАТ_ИМЯ = {А:'Годен', Б:'Годен с незначительными ограничениями', В:'Ограниченно годен', Г:'Временно не годен', Д:'Не годен'};
var КАТ_СМЫСЛ = {
  А:'Годен к службе без ограничений.',
  Б:'Служба возможна, с учётом ограничений.',
  В:'Освобождение от призыва в мирное время.',
  Г:'Отсрочка от призыва, обычно до 12 месяцев.',
  Д:'Исключение с воинского учёта.'
};
var ГЛАВЫ = [
  {имя:'Инфекции', а:1, б:7}, {имя:'Опухоли', а:8, б:10}, {имя:'Кровь и обмен веществ', а:11, б:15},
  {имя:'Психика', а:16, б:20}, {имя:'Нервы и мозг', а:21, б:28}, {имя:'Глаза', а:29, б:36},
  {имя:'Ухо, нос, горло', а:37, б:41}, {имя:'Сердце и сосуды', а:42, б:49}, {имя:'Лёгкие', а:50, б:53},
  {имя:'Желудок и кишечник', а:54, б:61}, {имя:'Кожа', а:62, б:65}, {имя:'Спина и суставы', а:66, б:70},
  {имя:'Почки и мочеполовые', а:71, б:78}, {имя:'Врождённое', а:79, б:81}, {имя:'После травм', а:82, б:85},
  {имя:'Прочее', а:86, б:88}
];
var ЗОНЫ = [
  {имя:'Нервы и психика', главы:['Нервы и мозг','Психика'], с:'п', x:152, y:22},
  {имя:'Глаза', главы:['Глаза'], с:'л', x:146, y:40},
  {имя:'Ухо, нос, горло', главы:['Ухо, нос, горло'], с:'п', x:150, y:66},
  {имя:'Лёгкие', главы:['Лёгкие'], с:'п', x:162, y:112},
  {имя:'Сердце и сосуды', главы:['Сердце и сосуды'], с:'л', x:140, y:116},
  {имя:'Живот', главы:['Желудок и кишечник'], с:'л', x:146, y:172},
  {имя:'Кожа', главы:['Кожа'], с:'п', x:198, y:176},
  {имя:'Почки и таз', главы:['Почки и мочеполовые'], с:'п', x:160, y:212},
  {имя:'Кровь', главы:['Кровь и обмен веществ'], с:'л', x:98, y:214},
  {имя:'Спина и суставы', главы:['Спина и суставы'], с:'л', x:136, y:318}
];
var ОБЩЕЕ = ['Инфекции','Опухоли','Врождённое','После травм','Прочее'];
var БЫТОВЫЕ = {диабет:'эндокрин', сахар:'эндокрин', щитовид:'щитовид', давлен:'гипер', серд:'серд', зрен:'глаз', глаз:'глаз', спин:'позвон', сустав:'сустав', желуд:'желуд', кашел:'дых', астм:'астм', кож:'кож', ухо:'слух', слух:'слух', почк:'почк'};
var ЧАСТЫЕ = ['диабет','давление','зрение','спина','плоскостопие','астма','щитовидка','депрессия'];

var ВХОДЫ = ['поиск','тело','исход'];
var сост = {вход:'поиск', статья:null, выбрано:null, ползунок:null};
var рез = {q:'', данные:null, ждём:false, ошибка:false};
var ДИАП34 = null;

function $(с){ return document.querySelector(с); }
function э(с){ return String(с == null ? '' : с).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function буква(г){ var м = /^[АБВГД]/.exec(String(г || '').trim().toUpperCase()); return м ? м[0] : null; }
function просто(н){
  var ч = String(н || '').split(',').map(function(т){ return т.trim(); }).filter(Boolean);
  if(!ч.length) return '';
  var т = ч[0];
  for(var i = 1; i < ч.length && т.length < 16; i++){ if((т + ', ' + ч[i]).length > 40) break; т = т + ', ' + ч[i]; }
  if(т.length > 46){ var ср = т.slice(0, 46), п = ср.lastIndexOf(' '); if(п > 24) т = ср.slice(0, п).replace(/[—–-]+$/, '').trim() + '…'; }
  return т;
}
function слово(н, а, б, в){ var д = н % 10, с = н % 100; return (д === 1 && с !== 11) ? а : (д >= 2 && д <= 4 && (с < 12 || с > 14)) ? б : в; }
function главаИмя(ид){ var н = parseInt(ид, 10); for(var i = 0; i < ГЛАВЫ.length; i++){ if(н >= ГЛАВЫ[i].а && н <= ГЛАВЫ[i].б) return ГЛАВЫ[i].имя; } return ''; }
function идыГлавы(имя){ var г = ГЛАВЫ.filter(function(х){ return х.имя === имя; })[0]; return г ? ИДЫ.filter(function(и){ var н = parseInt(и, 10); return н >= г.а && н <= г.б; }) : []; }

/* ---- категории статьи (графа I) ---- */
function катСтатьи(ид){
  var с = {А:0, Б:0, В:0, Г:0, Д:0};
  ((СТАТЬИ[ид] || {}).пункты || []).forEach(function(п){ var б = буква((п.графы || [])[0]); if(б) с[б]++; });
  return с;
}
function полоса(счёт, крупная){
  return '<div class="полоса'+(крупная ? ' крупная' : '')+'">'+КАТ.map(function(к){ return '<i class="к-'+к+(счёт[к] ? ' есть' : '')+'"></i>'; }).join('')+'</div>';
}
function счётОбласти(ид){
  var с = {А:0, Б:0, В:0, Г:0, Д:0};
  ид.forEach(function(и){ var к = катСтатьи(и); КАТ.forEach(function(б){ с[б] += к[б]; }); });
  return с;
}

/* ---- карточки ---- */
function карточка(ид, p){
  var а = СТАТЬИ[ид]; if(!а) return '';
  var п = просто(а.название), ф = String(а.название || '').trim();
  var сх = p == null ? '' : '<span class="сх">'+(p >= 0.8 ? 'очень близко' : p >= 0.5 ? 'близко' : p >= 0.2 ? 'возможно' : 'слабо')+'</span>';
  return '<button class="карт'+(p != null && p >= 0.5 ? ' лучшая' : '')+'" data-ст="'+ид+'">'+
    '<span class="н">ст. '+ид+' · '+э(главаИмя(ид))+'</span><span class="т">'+э(п)+'</span>'+
    (ф !== п ? '<span class="ф">'+э(ф)+'</span>' : '')+полоса(катСтатьи(ид))+сх+'</button>';
}
function списокСтатей(ид){ return '<div class="список">'+ид.map(function(и){ return карточка(и); }).join('')+'</div>'; }

/* ---- входы ---- */
function входПоиск(){
  var обл = ГЛАВЫ.map(function(г){
    var ид = идыГлавы(г.имя);
    return '<button class="обл" data-глава="'+э(г.имя)+'"><b>'+э(г.имя)+'</b><span>'+ид.length+' '+слово(ид.length, 'статья', 'статьи', 'статей')+'</span>'+полоса(счётОбласти(ид))+'</button>';
  }).join('');
  return '<div class="герой"><h2>Что беспокоит?</h2><p>Опишите словами — NNL найдёт статью Расписания и покажет, откуда берётся категория.</p>'+
    '<div class="чипы">'+ЧАСТЫЕ.map(function(ч){ return '<button class="чип" data-чип="'+э(ч)+'">'+э(ч)+'</button>'; }).join('')+'</div></div>'+
    '<h3 class="сек">По областям</h3><div class="области">'+обл+'</div>'+
    '<h3 class="сек">Права и порядок</h3><div class="права">'+
      '<details class="право"><summary>Сколько служить <small>12 месяцев</small></summary><p>Срок службы по призыву — 12 месяцев (ст. 38 ФЗ-53). Призывной возраст — 18–30 лет (ст. 22).</p></details>'+
      '<details class="право"><summary>Отсрочки <small>ст. 24</small></summary><p>Учёба, двое и больше детей, уход за близким, временная негодность по здоровью (категория Г).</p></details>'+
      '<details class="право"><summary>Решение можно обжаловать <small>комиссия или суд</small></summary><p>Решение призывной комиссии можно обжаловать в комиссии субъекта или в суде. Не затягивайте со сроками.</p></details>'+
    '</div>';
}
function входТело(){
  var нити = '', точки = '', метки = '';
  ЗОНЫ.forEach(function(з, i){
    var край = з.с === 'л' ? 78 : 222;
    нити += '<line class="нить" x1="'+з.x+'" y1="'+з.y+'" x2="'+край+'" y2="'+з.y+'"/>';
    точки += '<span class="точка" style="left:'+(з.x/3)+'%;top:'+(з.y/4.2)+'%"></span>';
    метки += '<button class="метка '+з.с+'" style="top:'+(з.y/4.2)+'%" data-зона="'+i+'">'+э(з.имя)+'</button>';
  });
  var силуэт =
    '<svg class="силуэт" viewBox="0 0 300 420" aria-hidden="true">'+
    '<g fill="var(--вст)" stroke="var(--волосок2)" stroke-width="1.2">'+
      '<circle cx="150" cy="42" r="24"/><rect x="142" y="60" width="16" height="26" rx="6"/>'+
      '<rect x="112" y="80" width="76" height="132" rx="26"/><rect x="118" y="196" width="64" height="54" rx="24"/>'+
      '<path d="M107 96 Q94 150 96 212" fill="none" stroke="var(--вст)" stroke-width="20" stroke-linecap="round"/>'+
      '<path d="M193 96 Q206 150 204 212" fill="none" stroke="var(--вст)" stroke-width="20" stroke-linecap="round"/>'+
      '<path d="M134 238 L131 398" fill="none" stroke="var(--вст)" stroke-width="28" stroke-linecap="round"/>'+
      '<path d="M166 238 L169 398" fill="none" stroke="var(--вст)" stroke-width="28" stroke-linecap="round"/>'+
    '</g>'+нити+'</svg>';
  return '<div class="герой"><h2>Где болит?</h2><p>Коснитесь подписи у нужного места — открою статьи этой области.</p></div>'+
    '<div class="тело">'+силуэт+точки+метки+'</div>'+
    '<h3 class="сек">Не привязано к месту</h3><div class="общее">'+ОБЩЕЕ.map(function(о){ return '<button class="чип" data-глава="'+э(о)+'">'+э(о)+'</button>'; }).join('')+'</div>';
}
function данныеИсходов(){
  var о = {А:{п:0, с:[]}, Б:{п:0, с:[]}, В:{п:0, с:[]}, Г:{п:0, с:[]}, Д:{п:0, с:[]}};
  ИДЫ.forEach(function(ид){ var с = катСтатьи(ид); КАТ.forEach(function(к){ if(с[к]){ о[к].п += с[к]; о[к].с.push({ид:ид, n:с[к]}); } }); });
  return о;
}
function входИсход(){
  var д = данныеИсходов(), макс = Math.max.apply(null, КАТ.map(function(к){ return д[к].п; }));
  return '<div class="герой"><h2>Что это даёт?</h2><p>Выберите итог — покажу все статьи, где он возможен для призывника.</p></div>'+
    '<div class="исходы">'+['Д','В','Г','Б','А'].map(function(к){
      var х = д[к];
      return '<button class="исход к-'+к+'" data-исход="'+к+'"><span class="бук">'+к+'</span><span><b>'+КАТ_ИМЯ[к]+'</b><span>'+КАТ_СМЫСЛ[к]+' В '+х.с.length+' '+слово(х.с.length, 'статье', 'статьях', 'статьях')+' · '+х.п+' '+слово(х.п, 'пункт', 'пункта', 'пунктов')+'</span><span class="шкала"><i style="width:'+Math.max(4, Math.round(100 * х.п / макс))+'%"></i></span></span></button>';
    }).join('')+'</div>';
}

/* ---- поиск ---- */
function запросУмный(){ var q = $('#запрос').value.trim(); return q.length >= 2; }
var таймер = null, счётчик = 0;
function искать(){
  clearTimeout(таймер);
  var q = $('#запрос').value.trim();
  $('#очист').hidden = !q;
  if(q.length < 2){ рез = {q:'', данные:null, ждём:false, ошибка:false}; нарисовать(); return; }
  var н = ++счётчик;
  рез.ждём = true; рез.q = q; нарисовать();
  таймер = setTimeout(function(){
    if(/^\d+$/.test(q)){ if(н === счётчик){ рез = {q:q, данные:null, ждём:false, ошибка:false, номер:true}; нарисовать(); } return; }
    fetch('/api/умныйпоиск?q=' + encodeURIComponent(q))
      .then(function(р){ if(!р.ok) throw new Error('нет'); return р.json(); })
      .then(function(д){ if(н !== счётчик) return; рез = {q:q, данные:д, ждём:false, ошибка:false}; нарисовать(); })
      .catch(function(){ if(н !== счётчик) return; рез = {q:q, данные:null, ждём:false, ошибка:true}; нарисовать(); });
  }, 260);
}
function местныйПоиск(q){
  q = q.toLowerCase();
  if(/^\d+$/.test(q)) return ИДЫ.filter(function(и){ return и.indexOf(q) === 0; });
  var ток = [q];
  Object.keys(БЫТОВЫЕ).forEach(function(к){ if(q.indexOf(к) !== -1) ток.push(БЫТОВЫЕ[к]); });
  return ИДЫ.filter(function(и){ var н = String(СТАТЬИ[и].название || '').toLowerCase(); return ток.some(function(т){ return н.indexOf(т) !== -1; }); });
}
function результаты(){
  var q = рез.q, д = рез.данные, ч = [];
  var м = местныйПоиск(q);
  if(рез.номер) return м.length ? '<h3 class="сек">Найдено по номеру</h3>'+списокСтатей(м) : '<p class="пусто">Такой статьи нет.</p>';
  if(рез.ошибка){
    return '<p class="пусто">Умный поиск не отвечает — ищу по словам в названиях.</p>'+(м.length ? списокСтатей(м) : '');
  }
  if(!д || д.запрос !== q){
    return '<h3 class="сек">Ищу по смыслу <span class="н">NNL</span></h3>'+(м.length ? списокСтатей(м) : '<p class="пусто">Думаю над фразой…</p>');
  }
  if(д.статьи && д.статьи.length){
    ч.push('<h3 class="сек">Ближе всего по смыслу <span class="н">NNL</span></h3><div class="список">'+д.статьи.map(function(а){ return карточка(а.ид, а.p); }).join('')+'</div>');
  }
  if(д.право && д.право.length){
    ч.push('<h3 class="сек">Это про права <span class="н">NNL</span></h3><div class="права">'+д.право.map(function(т){ return '<details class="право"><summary>'+э(т.название)+'</summary><p>'+э(т.суть)+'</p></details>'; }).join('')+'</div>');
  }
  if(д.вне_темы){
    ч.push('<p class="пусто">NNL не нашёл здесь ни статей, ни прав: похоже, фраза не про здоровье и не про воинский учёт.</p>');
    if(м.length) ч.push('<h3 class="сек">По словам в названиях</h3>'+списокСтатей(м));
  }
  return ч.join('');
}

/* ---- отрисовка главной ---- */
function нарисовать(){
  var э_ = $('#экран'), ск = э_.scrollTop;
  $('#мета-к').querySelectorAll('button').forEach(function(б){ б.classList.toggle('он', б.getAttribute('data-вход') === сост.вход); });
  if(рез.q && рез.q.length >= 2) э_.innerHTML = результаты();
  else э_.innerHTML = сост.вход === 'тело' ? входТело() : сост.вход === 'исход' ? входИсход() : входПоиск();
  if(рез.q) э_.scrollTop = ск;
}

/* ---- лист ---- */
function листОткрыть(з, п, html){
  $('#лист-з').textContent = з; $('#лист-п').textContent = п || ''; $('#лист-т').innerHTML = html;
  $('#лист').classList.add('он'); $('#фон-л').classList.add('он'); $('#лист-т').scrollTop = 0;
}
function листЗакрыть(){ $('#лист').classList.remove('он'); $('#фон-л').classList.remove('он'); }
function листГлав(имена, заг){
  var всего = 0, html = имена.map(function(им){
    var ид = идыГлавы(им); всего += ид.length;
    return (имена.length > 1 ? '<h3 class="подгл">'+э(им)+'</h3>' : '')+списокСтатей(ид);
  }).join('');
  листОткрыть(заг, всего + ' ' + слово(всего, 'статья', 'статьи', 'статей'), html);
}

/* ---- страница статьи ---- */
function цветаПорога(диап){
  var макс = 16, стопы = [];
  диап.forEach(function(д){
    var лево = (макс - Math.min(макс, д.до == null ? макс : д.до)) / макс * 100, право = (макс - д.более) / макс * 100;
    var к = буква(д.категория);
    var цвет = к ? 'var(--к' + к + ')' : 'var(--волосок2)';
    стопы.push(цвет + ' ' + лево.toFixed(1) + '% ' + право.toFixed(1) + '%');
  });
  if(диап.length){ var мин = Math.min.apply(null, диап.map(function(д){ return д.более; })); стопы.push('var(--волосок2) ' + ((макс - мин) / макс * 100).toFixed(1) + '% 100%'); }
  return 'linear-gradient(90deg,' + (стопы.length ? стопы.join(',') : 'var(--волосок)') + ')';
}
function порогПоЗначению(диап, v){
  for(var i = 0; i < диап.length; i++){ var д = диап[i]; if(v > д.более && (д.до == null || v <= д.до)) return д; }
  return null;
}
function ползунокHtml(){
  return '<section class="блок" id="блок-ползунок"><h3>Сколько у вас диоптрий?</h3><p class="под">Двигайте ползунок: пункт и категория меняются по порогам из текста статьи. Это для близорукости и дальнозоркости, астигматизм считается отдельно.</p>'+
    '<div class="ползунок"><div class="значение"><b id="пз-число">−7,0</b><span>дптр</span></div>'+
    '<input type="range" id="пз" min="-16" max="0" step="0.5" value="-7" aria-label="Диоптрии"><div id="пз-итог"></div></div></section>';
}
function ползунокОбновить(){
  var пз = $('#пз'); if(!пз || !ДИАП34) return;
  var v = Math.abs(parseFloat(пз.value)), п = порогПоЗначению(ДИАП34, v);
  $('#пз-число').textContent = (v === 0 ? '0' : '−' + v.toFixed(1).replace('.', ',')).replace('0,0', '0');
  var итог = $('#пз-итог');
  document.querySelectorAll('.ступень').forEach(function(с){ с.classList.remove('подсвечена'); });
  document.querySelectorAll('.шк').forEach(function(с){ с.classList.remove('мерцает'); });
  if(п){
    var к = буква(п.категория);
    итог.innerHTML = '<div class="итог к-'+к+'"><div class="бук">'+э(п.категория)+'</div><div><b>Пункт «'+э(п.пункт)+'» → категория '+э(п.категория)+'</b><span>'+КАТ_СМЫСЛ[к]+' Врач подтверждает измерением.</span></div></div>';
    document.querySelectorAll('.ступень[data-буква="'+п.пункт+'"]').forEach(function(с){ с.classList.add('подсвечена'); });
    var шк = document.querySelector('.шк.к-'+к); if(шк) шк.classList.add('мерцает');
  } else {
    итог.innerHTML = '<div class="итог"><div class="бук">—</div><div><b>Ниже порога этой статьи</b><span>Меньше 3 дптр — по этой статье ограничений нет.</span></div></div>';
  }
}
function загрузитьДиап34(после){
  if(ДИАП34){ после(); return; }
  fetch('/api/ст34?дптр=0').then(function(р){ if(!р.ok) throw 0; return р.json(); })
    .then(function(д){ ДИАП34 = д.диапазоны; }).catch(function(){
      ДИАП34 = [{более:12, до:null, пункт:'а', категория:'Д'}, {более:8, до:12, пункт:'б', категория:'В'}, {более:6, до:8, пункт:'в', категория:'В'}, {более:3, до:6, пункт:'г', категория:'Б-3'}];
    }).then(после);
}
function открытьСтатью(ид){
  var а = СТАТЬИ[ид]; if(!а) return;
  сост.статья = ид; сост.выбрано = null;
  var п = просто(а.название), ф = String(а.название || '').trim(), к = катСтатьи(ид);
  var пунктыУпор = (а.пункты || []).map(function(пт, i){ return {пт:пт, i:i, б:буква((пт.графы || [])[0])}; })
    .sort(function(x, y){ return (КАТ.indexOf(y.б) - КАТ.indexOf(x.б)) || (x.i - y.i); });
  var шк = '<div class="шкала-кат">'+КАТ.map(function(х){ return '<div class="шк к-'+х+(к[х] ? ' есть' : '')+'"><b>'+х+'</b><small>'+(к[х] ? к[х] + ' ' + слово(к[х], 'пункт', 'пункта', 'пунктов') : '—')+'</small></div>'; }).join('')+'</div>'+
    '<p class="подпись-шкалы">Графа I — призывник. Нажмите ступень ниже: покажу, что она значит.</p>';
  var ступени = пунктыУпор.map(function(о){
    var г0 = (о.пт.графы || [])[0] || '', б = о.б;
    return '<button class="ступень'+(б ? ' к-'+б : '')+'" data-ступень="'+о.i+'" data-буква="'+э(о.пт.буква)+'"><span class="узел">'+(б || '·')+'</span>'+
      '<span class="кирп"><span class="п">пункт «'+э(о.пт.буква)+'»'+(г0 ? ' · графа I: <em>'+э(г0)+'</em>' : '')+'</span><p>'+э(о.пт.описание).replace(/(\d+(?:[.,]\d+)?)/g, '<b>$1</b>')+'</p><span class="отметка">Это про меня</span></span></button>';
  }).join('');
  var прим = (а.примечания || []).filter(function(т){ return !/^\(в ред\./.test(т) && !/^\(абзац/.test(т); }).slice(0, 8);
  var i = ИДЫ.indexOf(ид);
  $('#ст-путь').textContent = 'Справочник › ' + главаИмя(ид);
  $('#пред').disabled = i <= 0; $('#след').disabled = i >= ИДЫ.length - 1;
  $('#ст-тело').innerHTML =
    '<p class="ст-над">Статья '+ид+' · ПП РФ № 565</p><h1>'+э(п)+'</h1>'+(ф !== п ? '<p class="ст-ф">'+э(ф)+'</p>' : '')+шк+
    (ид === '34' ? ползунокHtml() : '')+
    '<div class="лесенка"><h3>Ступени — от тяжёлого к лёгкому</h3>'+ступени+'</div>'+
    (прим.length ? '<details class="важно"><summary>Важно</summary>'+прим.map(function(т){ return '<p>'+э(т)+'</p>'; }).join('')+'</details>' : '')+
    '<section class="блок спросить"><h3>Спросить статью</h3><p class="под">Отвечу только по тексту этой статьи и покажу цитаты. Числа проверяются по документу.</p>'+
    '<div class="строка"><input id="вопрос" type="text" placeholder="Например: что считается незначительным нарушением?" autocomplete="off"><button class="идти" id="идти">Спросить</button></div><div id="ответ"></div></section>';
  нижняяПанель();
  $('#ст-тело').scrollTop = 0;
  $('#статья').classList.add('он');
  try{ history.replaceState(null, '', '#ст' + ид); }catch(е){}
  if(ид === '34') загрузитьДиап34(function(){
    var пз = $('#пз'); if(!пз) return;
    пз.style.setProperty('--трек', цветаПорога(ДИАП34));
    пз.addEventListener('input', ползунокОбновить); ползунокОбновить();
  });
}
function вДеле(ид){ try{ return (JSON.parse(localStorage.getItem('концепт_дело') || '[]')).indexOf(ид) !== -1; }catch(е){ return false; } }
function дело(ид, вкл){
  try{
    var с = JSON.parse(localStorage.getItem('концепт_дело') || '[]'), и = с.indexOf(ид);
    if(вкл && и === -1) с.push(ид); if(!вкл && и !== -1) с.splice(и, 1);
    localStorage.setItem('концепт_дело', JSON.stringify(с));
  }catch(е){}
}
function нижняяПанель(){
  var ид = сост.статья, к = сост.выбрано, ч = '';
  if(к){
    ч += '<div class="реш к-'+к+'"><span class="бук">'+к+'</span><div><b>Если врач подтвердит — категория '+к+': '+КАТ_ИМЯ[к].toLowerCase()+'</b><span>'+КАТ_СМЫСЛ[к]+' Категорию назначает врач по документам.</span></div></div>';
  }
  ч += '<div class="действия"><button class="д-к'+(вДеле(ид) ? ' он' : ' гл')+'" id="д-дело">'+(вДеле(ид) ? 'В моём деле' : 'Добавить в моё дело')+'</button><button class="д-к" id="д-бумага">Подать заявление</button></div>';
  $('#ст-низ').innerHTML = ч;
}
function закрытьСтатью(){
  $('#статья').classList.remove('он'); сост.статья = null; сост.выбрано = null;
  try{ history.replaceState(null, '', location.pathname + location.search); }catch(е){}
}
function спросить(){
  var в = $('#вопрос').value.trim(), ид = сост.статья; if(!в) return;
  var о = $('#ответ'); о.innerHTML = '<p class="ответ" style="color:var(--тише)">Читаю статью…</p>';
  fetch('/api/читатель', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ид:ид, вопрос:в})})
    .then(function(р){ return р.json(); })
    .then(function(д){
      if(д.ошибка){ о.innerHTML = '<p class="ответ" style="color:var(--кД)">'+э(д.ошибка)+'</p>'; return; }
      о.innerHTML = '<p class="ответ">'+э(д.ответ)+'</p>'+(д.цитаты || []).map(function(ц){ return '<div class="цитата">«'+э(ц.текст)+'»<i>'+(ц.подтверждена ? '✓ есть в статье' : 'не найдена')+'</i></div>'; }).join('');
    }).catch(function(){ о.innerHTML = '<p class="ответ" style="color:var(--кД)">Сервер NNL не ответил: вопрос по статье нужна модель на сервере.</p>'; });
}

/* ---- события ---- */
function тост(т){ var т_ = $('#тост'); т_.textContent = т; т_.classList.add('он'); clearTimeout(тост.т); тост.т = setTimeout(function(){ т_.classList.remove('он'); }, 1800); }
document.addEventListener('click', function(е){
  var т = е.target.closest ? е.target : null; if(!т) return;
  var б;
  if((б = т.closest('[data-вход]'))){ сост.вход = б.getAttribute('data-вход'); $('#запрос').value = ''; рез = {q:'', данные:null, ждём:false, ошибка:false}; $('#очист').hidden = true; нарисовать(); $('#экран').scrollTop = 0; return; }
  if((б = т.closest('[data-ст]'))){ листЗакрыть(); открытьСтатью(б.getAttribute('data-ст')); return; }
  if((б = т.closest('[data-глава]'))){ var им = б.getAttribute('data-глава'); листГлав([им], им); return; }
  if((б = т.closest('[data-зона]'))){ var з = ЗОНЫ[parseInt(б.getAttribute('data-зона'), 10)]; листГлав(з.главы, з.имя); return; }
  if((б = т.closest('[data-исход]'))){
    var к = б.getAttribute('data-исход'), д = данныеИсходов()[к];
    var сорт = д.с.slice().sort(function(x, y){ return y.n - x.n || ПОНОМЕРУ(x.ид, y.ид); });
    листОткрыть(к + ' · ' + КАТ_ИМЯ[к], сорт.length + ' ' + слово(сорт.length, 'статья', 'статьи', 'статей'), '<p class="пусто" style="padding-top:2px">'+КАТ_СМЫСЛ[к]+' Сверху статьи, где таких пунктов больше.</p>'+списокСтатей(сорт.map(function(х){ return х.ид; })));
    return;
  }
  if((б = т.closest('[data-чип]'))){ $('#запрос').value = б.getAttribute('data-чип'); искать(); return; }
  if((б = т.closest('[data-таб]'))){ if(б.getAttribute('data-таб') !== 'справочник') тост('В концепте рисую только Справочник'); return; }
  if((б = т.closest('[data-ступень]'))){
    var н = б.getAttribute('data-ступень'), бук = (СТАТЬИ[сост.статья].пункты[parseInt(н, 10)].графы || [])[0];
    var кат = буква(бук), уже = б.classList.contains('выбрана');
    document.querySelectorAll('.ступень').forEach(function(с){ с.classList.remove('выбрана'); });
    if(уже || !кат){ сост.выбрано = null; } else { б.classList.add('выбрана'); сост.выбрано = кат; }
    нижняяПанель(); return;
  }
  if(т.closest('#назад')){ закрытьСтатью(); return; }
  if(т.closest('#пред')){ var и = ИДЫ.indexOf(сост.статья); if(и > 0) открытьСтатью(ИДЫ[и - 1]); return; }
  if(т.closest('#след')){ var и2 = ИДЫ.indexOf(сост.статья); if(и2 < ИДЫ.length - 1) открытьСтатью(ИДЫ[и2 + 1]); return; }
  if(т.closest('#д-дело')){ var вкл = !вДеле(сост.статья); дело(сост.статья, вкл); нижняяПанель(); тост(вкл ? 'Добавлено в дело' : 'Убрано из дела'); return; }
  if(т.closest('#д-бумага')){ тост('Бумаги в концепте не рисую'); return; }
  if(т.closest('#идти')){ спросить(); return; }
  if(т.closest('#очист')){ $('#запрос').value = ''; искать(); $('#запрос').focus(); return; }
  if(т.closest('#фон-л')){ листЗакрыть(); return; }
});
document.addEventListener('keydown', function(е){
  if(е.key === 'Enter' && е.target && е.target.id === 'вопрос'){ е.preventDefault(); спросить(); }
  if(е.key === 'Escape'){ if($('#лист').classList.contains('он')) листЗакрыть(); else if(сост.статья) закрытьСтатью(); }
});
$('#запрос').addEventListener('input', искать);

/* ---- старт ---- */
нарисовать();
fetch('/api/умныйпоиск?q=' + encodeURIComponent('тест')).then(function(р){ if(р.ok) $('#ядро').classList.add('жив'); }).catch(function(){});
var м = /^#ст(\d+)$/.exec(decodeURIComponent(location.hash)); if(м && СТАТЬИ[м[1]]) открытьСтатью(м[1]);
})();
