/* Карточка «Проверьте себя» на странице статьи: чеклист подтверждения, ползунки по порогам, признаки поражения, исключения.
   Данные: window.КАРТОЧКИ_СТАТЕЙ (файл карточки_статей.js собирает карточки/собрать.py; каждая строка опирается на цитату из текста статьи).
   Карточка встаёт в заглушку #карточка-статьи, которую страница статьи кладёт под калькулятором. Отметки хранятся на устройстве.
   Это ориентир по тексту статьи, а не решение: пункт и категорию определяет врач. */
(function(){
'use strict';

var ХРАНИЛИЩЕ = 'справка_карточка_';

function э(с){ return String(с == null ? '' : с).replace(/[&<>"']/g, function(к){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[к]; }); }
function число(v){ return String(v).replace('.', ','); }

function читать(ид){ try{ return JSON.parse(localStorage.getItem(ХРАНИЛИЩЕ + ид) || '{}') || {}; }catch(е){ return {}; } }
function писать(ид, с){ try{ localStorage.setItem(ХРАНИЛИЩЕ + ид, JSON.stringify(с)); }catch(е){} }

/* порядок пунктов от тяжёлого к лёгкому и категории берём со страницы статьи: она уже построена по тексту */
function порядокПунктов(){
  return Array.prototype.map.call(document.querySelectorAll('.лесенка .ступень'), function(с){ return с.getAttribute('data-буква'); });
}
function тяжесть(б, порядок){ var i = порядок.indexOf(б); return i === -1 ? 99 : i; }
function категория(б){
  var у = document.querySelector('.лесенка .ступень[data-буква="' + б + '"] .узел');
  return у ? у.textContent.trim() : '';
}
function тяжелейший(буквы){
  var пор = порядокПунктов(), л = null;
  буквы.forEach(function(б){ if(!б) return; if(л === null || тяжесть(б, пор) < тяжесть(л, пор)) л = б; });
  return л;
}
function строкаПункта(б){
  var к = категория(б);
  return 'пункт «' + э(б) + '»' + (к && к !== '·' ? ' · категория ' + э(к) : '');
}

function подробнее(ц){ return ц ? '<details class="кс-цитата"><summary>В тексте статьи</summary><blockquote>«' + э(ц) + '»</blockquote></details>' : ''; }

/* --- блоки --- */
function htmlЧеклист(б, i, с){
  var отм = (с.чек && с.чек[i]) || {};
  var всего = б.пункты.length, есть = б.пункты.filter(function(_, j){ return отм[j]; }).length;
  return '<div class="кс-блок"><h4>' + э(б.заг) + '</h4>' + (б.пояснение ? '<p class="кс-под">' + э(б.пояснение) + '</p>' : '') +
    '<div class="кс-спис">' + б.пункты.map(function(п, j){
      return '<div class="кс-стр' + (отм[j] ? ' он' : '') + '"><button type="button" class="кс-чек" role="checkbox" aria-checked="' + (отм[j] ? 'true' : 'false') + '" data-кс-чек="' + i + ':' + j + '">' +
        '<i aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></i><span>' + э(п.текст) + '</span></button>' + подробнее(п.цитата) + '</div>';
    }).join('') + '</div>' +
    '<div class="кс-счёт"><div class="кс-шкала"><u style="width:' + Math.round(100 * есть / всего) + '%"></u></div><span>На руках ' + есть + ' из ' + всего + '</span></div></div>';
}
function значенияПолей(б, i, с){
  var зн = (с.пол && с.пол[i]) || {}, вых = {};
  б.поля.forEach(function(п){ вых[п.ключ] = зн[п.ключ] != null ? зн[п.ключ] : п.знач; });
  return вых;
}
function подошедшиеПравила(б, зн){
  return б.правила.filter(function(р){
    var усл = Object.keys(р.когда || {}).map(function(к){
      var у = р.когда[к], v = зн[к];
      return v != null && (у.от == null || v >= у.от) && (у.до == null || v <= у.до) && (у.больше == null || v > у.больше) && (у.меньше == null || v < у.меньше);
    });
    if(!усл.length) return false;
    return (р.режим === 'или') ? усл.some(Boolean) : усл.every(Boolean);
  });
}
function htmlПолзунок(б, i, с){
  var зн = значенияПолей(б, i, с), пр = подошедшиеПравила(б, зн);
  var пор = порядокПунктов();
  пр.sort(function(а, в){ return тяжесть(а.пункт, пор) - тяжесть(в.пункт, пор); });
  var лучший = пр[0];
  return '<div class="кс-блок"><h4>' + э(б.заг) + '</h4>' + (б.пояснение ? '<p class="кс-под">' + э(б.пояснение) + '</p>' : '') +
    б.поля.map(function(п){
      return '<div class="кс-поле"><div class="кс-зн"><b>' + число(зн[п.ключ]) + '</b><span>' + э(п.подпись) + ' · ' + э(п.ед) + '</span></div>' +
        '<input type="range" data-кс-пол="' + i + ':' + э(п.ключ) + '" min="' + п.мин + '" max="' + п.макс + '" step="' + п.шаг + '" value="' + зн[п.ключ] + '" aria-label="' + э(п.подпись) + '"></div>';
    }).join('') +
    '<div class="кс-итог ' + (лучший ? 'есть' : 'нет') + '">' + (лучший
      ? '<b>По этим числам: ' + строкаПункта(лучший.пункт) + '</b><span>' + э(лучший.текст) + '</span>' + подробнее(лучший.цитата) +
        '<button type="button" class="кс-ссылка" data-кс-ступень="' + э(лучший.пункт) + '">Показать ступень в статье</button>'
      : '<b>Ниже порогов этой статьи</b><span>По этим числам ни один пункт не называется. Решает врач.</span>') + '</div></div>';
}
function htmlПризнаки(б, i, с){
  var отм = (с.приз && с.приз[i]) || {};
  var выбр = б.варианты.filter(function(_, j){ return отм[j]; });
  var л = тяжелейший(выбр.map(function(в){ return в.пункт; }));
  return '<div class="кс-блок"><h4>' + э(б.заг) + '</h4>' + (б.пояснение ? '<p class="кс-под">' + э(б.пояснение) + '</p>' : '') +
    '<div class="кс-спис">' + б.варианты.map(function(в, j){
      return '<div class="кс-стр' + (отм[j] ? ' он' : '') + '"><button type="button" class="кс-чек" role="checkbox" aria-checked="' + (отм[j] ? 'true' : 'false') + '" data-кс-приз="' + i + ':' + j + '">' +
        '<i aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></i><span>' + э(в.текст) + (в.пункт ? ' <em>пункт «' + э(в.пункт) + '»</em>' : '') + '</span></button>' +
        (в.обследование ? '<p class="кс-обс">Чем подтверждается: ' + э(в.обследование) + '</p>' : '') + подробнее(в.цитата) + '</div>';
    }).join('') + '</div>' +
    '<div class="кс-итог ' + (выбр.length ? 'есть' : 'нет') + '">' + (выбр.length
      ? '<b>Выбрано признаков: ' + выбр.length + (л ? '. Тяжелее всего указывает на ' + строкаПункта(л) : '') + '</b><span>Это то, что указывает на пункт, а не вывод: нужен документ врача.</span>' +
        (л ? '<button type="button" class="кс-ссылка" data-кс-ступень="' + э(л) + '">Показать ступень в статье</button>' : '')
      : '<b>Ничего не выбрано</b><span>Отметьте то, что у вас подтверждено документами.</span>') + '</div></div>';
}
function htmlИсключение(б, i, с){
  var да = !!(с.искл && с.искл[i]);
  return '<div class="кс-блок кс-искл"><h4>' + э(б.заг) + '</h4><p class="кс-под">' + э(б.текст) + '</p>' + подробнее(б.цитата) +
    '<div class="кс-кн"><button type="button" class="' + (да ? 'он' : '') + '" data-кс-искл="' + i + ':1">Да, это про меня</button><button type="button" class="' + (!да ? 'он' : '') + '" data-кс-искл="' + i + ':0">Нет</button></div>' +
    (да ? '<div class="кс-итог есть"><b>Тогда смотрите статью ' + э(б.статья) + '</b><span>Для этого случая освидетельствование проводится по другой статье.</span>' +
      '<button type="button" class="кс-ссылка" data-кс-статья="' + э(б.статья) + '">Открыть ст. ' + э(б.статья) + '</button></div>' : '') + '</div>';
}
function htmlСводка(к, с){
  var стр = [];
  к.блоки.forEach(function(б, i){
    if(б.вид === 'чеклист'){
      var отм = (с.чек && с.чек[i]) || {}, нет = б.пункты.filter(function(_, j){ return !отм[j]; });
      if(!нет.length) стр.push('<li class="ок">Документы из списка «' + э(б.заг) + '» у вас на руках.</li>');
      else стр.push('<li>Не хватает документов (' + нет.length + ' из ' + б.пункты.length + '): ' + нет.map(function(п){ return э(п.текст); }).join('; ') + '.</li>');
    }
  });
  if(!стр.length) return '';
  return '<div class="кс-свод"><b>Итог по вашим отметкам</b><ul>' + стр.join('') + '</ul></div>';
}

function htmlКарточка(ид, к){
  var с = читать(ид);
  var ч = ['<div class="кс-шапка"><h3>Проверьте себя</h3><span class="кс-метка ' + (к.статус === 'проверено' ? 'пр' : 'чр') + '">' +
    (к.статус === 'проверено' ? 'проверено' : 'черновик') + '</span></div>' +
    (к.статус === 'проверено' ? '' : '<p class="кс-под">Составлено по тексту статьи, врач не проверял. У каждой строки есть цитата из статьи.</p>')];
  к.блоки.forEach(function(б, i){
    ч.push(б.вид === 'чеклист' ? htmlЧеклист(б, i, с) : б.вид === 'ползунок' ? htmlПолзунок(б, i, с) : б.вид === 'признаки' ? htmlПризнаки(б, i, с) : htmlИсключение(б, i, с));
  });
  ч.push(htmlСводка(к, с));
  ч.push('<p class="кс-сноска">Это ориентир по тексту статьи, а не решение. Пункт и категорию определяет врач.</p>');
  return ч.join('');
}

function показать(место){
  var ид = место.getAttribute('data-ид'), к = (window.КАРТОЧКИ_СТАТЕЙ || {})[ид];
  if(!к || !к.блоки || !к.блоки.length){ место.innerHTML = ''; место.classList.remove('кс'); return; }
  место.classList.add('кс');
  место.innerHTML = htmlКарточка(ид, к);
  место._карточка = к; место._ид = ид;
}

function при(место, е){
  var ц = е.target.closest ? е.target : null; if(!ц) return;
  var ид = место._ид, с = читать(ид), к;
  if((к = ц.closest('[data-кс-чек]'))){
    var [i, j] = к.getAttribute('data-кс-чек').split(':'); с.чек = с.чек || {}; с.чек[i] = с.чек[i] || {}; с.чек[i][j] = !с.чек[i][j];
    писать(ид, с); показать(место); return;
  }
  if((к = ц.closest('[data-кс-приз]'))){
    var [i2, j2] = к.getAttribute('data-кс-приз').split(':'); с.приз = с.приз || {}; с.приз[i2] = с.приз[i2] || {}; с.приз[i2][j2] = !с.приз[i2][j2];
    писать(ид, с); показать(место); return;
  }
  if((к = ц.closest('[data-кс-искл]'))){
    var [i3, v] = к.getAttribute('data-кс-искл').split(':'); с.искл = с.искл || {}; с.искл[i3] = v === '1';
    писать(ид, с); показать(место); return;
  }
  if((к = ц.closest('[data-кс-ступень]'))){
    var ст = document.querySelector('.лесенка .ступень[data-буква="' + к.getAttribute('data-кс-ступень') + '"]');
    if(ст){ ст.classList.add('по-словам'); ст.scrollIntoView({behavior: 'smooth', block: 'center'}); }
    return;
  }
  if((к = ц.closest('[data-кс-статья]'))){
    var б = document.createElement('button'); б.setAttribute('data-статья', к.getAttribute('data-кс-статья')); б.style.cssText = 'position:fixed;left:-9999px';
    document.body.appendChild(б); б.click(); б.remove(); return;
  }
}
function при_ввод(место, е){
  var р = е.target.closest ? e0(е.target, '[data-кс-пол]') : null; if(!р) return;
  var [i, ключ] = р.getAttribute('data-кс-пол').split(':'), ид = место._ид, с = читать(ид);
  с.пол = с.пол || {}; с.пол[i] = с.пол[i] || {}; с.пол[i][ключ] = parseFloat(р.value);
  писать(ид, с);
  /* перерисовываем без потери перетаскивания: заменяем только итог и подписи значений */
  var поз = р.parentElement; var зн = поз.querySelector('.кс-зн b'); if(зн) зн.textContent = число(р.value);
  var блок = р.closest('.кс-блок'), к = место._карточка, б = к.блоки[parseInt(i, 10)];
  var нов = document.createElement('div'); нов.innerHTML = htmlПолзунок(б, parseInt(i, 10), с);
  var итог = блок.querySelector('.кс-итог'), новый = нов.querySelector('.кс-итог');
  if(итог && новый) итог.replaceWith(новый);
  var св = место.querySelector('.кс-свод'); if(св){ var н2 = document.createElement('div'); н2.innerHTML = htmlСводка(к, с); if(н2.firstChild) св.replaceWith(н2.firstChild); }
}
function e0(эл, сел){ return эл.closest(сел); }

function осмотреть(узел){
  var места = [];
  if(узел.nodeType !== 1) return;
  if(узел.id === 'карточка-статьи') места.push(узел);
  if(узел.querySelectorAll) Array.prototype.forEach.call(узел.querySelectorAll('#карточка-статьи'), function(м){ места.push(м); });
  места.forEach(function(м){
    if(м._слушает) { показать(м); return; }
    м._слушает = true;
    м.addEventListener('click', function(е){ при(м, е); });
    м.addEventListener('input', function(е){ при_ввод(м, е); });
    показать(м);
  });
}

function старт(){
  new MutationObserver(function(ряд){ ряд.forEach(function(р){ Array.prototype.forEach.call(р.addedNodes, осмотреть); }); }).observe(document.body, {childList: true, subtree: true});
  осмотреть(document.body);
}
if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', старт); else старт();
})();
