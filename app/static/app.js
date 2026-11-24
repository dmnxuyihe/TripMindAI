'use strict';
const $ = id => document.getElementById(id);
const state = {tab:'chat', conversationId:null, model:'qwen-plus', models:[], tasks:new Map(), mapConfig:null, currentPlan:null};
const SEVERITIES = {critical:'致命',major:'严重',minor:'一般',suggestion:'建议'};
const STATUSES = {open:'待处理',fixed:'已修复',verified:'已复测',wontfix:'暂不修复'};
const TABS = {chat:'AI 对话',plan:'行程规划',lab:'算法实验室',defects:'测试与缺陷'};

async function api(path, options={}){
  const timeout=options.timeout||45000;
  const controller=new AbortController();
  const timer=setTimeout(function(){controller.abort();},timeout);
  try{
    const res = await fetch(path,{...options,signal:controller.signal,headers:{'Content-Type':'application/json',...(options.headers||{})}});
    let json;
    try{json=await res.json();}catch(e){throw Error(`服务器返回非 JSON（HTTP ${res.status}）`);}
    if(!res.ok){const detail=json.detail;throw Error(typeof detail==='string'?detail:JSON.stringify(detail||`HTTP ${res.status}`));}
    return json;
  }catch(err){
    if(err&&err.name==='AbortError')throw Error('请求超时（'+(timeout/1000)+' 秒），请稍后重试');
    throw err;
  }finally{clearTimeout(timer);}
}
let toastTimer;
function toast(message){const el=$('toast');el.textContent=message;el.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.hidden=true,5000);}
function node(tag,className,text){const el=document.createElement(tag);if(className)el.className=className;if(text!==undefined)el.textContent=text;return el;}
function add(parent,...children){children.forEach(child=>parent.appendChild(child));return parent;}
function renderInline(parent,text){const pattern=/(\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|\*\*([^*\n]+)\*\*|`([^`\n]+)`|\*([^*\n]+)\*)/g;let last=0,match;while((match=pattern.exec(text))){if(match.index>last)parent.appendChild(document.createTextNode(text.slice(last,match.index)));if(match[2]){const a=node('a','markdown-link',match[2]);a.href=match[3];a.target='_blank';a.rel='noopener noreferrer';parent.appendChild(a);}else if(match[4])parent.appendChild(node('strong','',match[4]));else if(match[5])parent.appendChild(node('code','inline-code',match[5]));else if(match[6])parent.appendChild(node('em','',match[6]));last=pattern.lastIndex;}if(last<text.length)parent.appendChild(document.createTextNode(text.slice(last)));}
function tableCells(line){let value=line.trim();if(value.startsWith('|'))value=value.slice(1);if(value.endsWith('|'))value=value.slice(0,-1);return value.split('|').map(x=>x.trim());}
function isTableDivider(line){return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);}
function renderRichText(parent,text){const lines=String(text||'').replace(/\r/g,'').split('\n');let i=0;while(i<lines.length){const line=lines[i];if(!line.trim()){i++;continue;}if(line.trim().startsWith('```')){const language=line.trim().slice(3),code=[];i++;while(i<lines.length&&!lines[i].trim().startsWith('```'))code.push(lines[i++]);if(i<lines.length)i++;const pre=node('pre','code-block'),c=node('code','',code.join('\n'));if(language)c.dataset.language=language;pre.appendChild(c);parent.appendChild(pre);continue;}if(line.includes('|')&&i+1<lines.length&&isTableDivider(lines[i+1])){const headers=tableCells(line),aligns=tableCells(lines[i+1]),wrap=node('div','markdown-table-wrap'),table=node('table','markdown-table'),thead=node('thead'),headRow=node('tr');headers.forEach((value,index)=>{const th=node('th');renderInline(th,value);if(aligns[index]?.startsWith(':')&&aligns[index]?.endsWith(':'))th.style.textAlign='center';else if(aligns[index]?.endsWith(':'))th.style.textAlign='right';headRow.appendChild(th);});thead.appendChild(headRow);table.appendChild(thead);i+=2;const tbody=node('tbody');while(i<lines.length&&lines[i].includes('|')&&lines[i].trim()){const tr=node('tr');tableCells(lines[i]).forEach((value,index)=>{const td=node('td');renderInline(td,value);if(aligns[index]?.startsWith(':')&&aligns[index]?.endsWith(':'))td.style.textAlign='center';else if(aligns[index]?.endsWith(':'))td.style.textAlign='right';tr.appendChild(td);});tbody.appendChild(tr);i++;}table.appendChild(tbody);wrap.appendChild(table);parent.appendChild(wrap);continue;}const heading=line.match(/^(#{1,4})\s+(.+)$/);if(heading){const h=node('h'+heading[1].length,'markdown-heading');renderInline(h,heading[2]);parent.appendChild(h);i++;continue;}const orderedMatch=line.match(/^\s*(\d+)[.)]\s+(.+)$/),bulletMatch=line.match(/^\s*[-*+]\s+(.+)$/);if(orderedMatch||bulletMatch){const ordered=Boolean(orderedMatch),list=node(ordered?'ol':'ul','markdown-list');if(ordered)list.start=Number(orderedMatch[1]);while(i<lines.length){const match=ordered?lines[i].match(/^\s*(\d+)[.)]\s+(.+)$/):lines[i].match(/^\s*[-*+]\s+(.+)$/);if(!match)break;const li=node('li');renderInline(li,ordered?match[2]:match[1]);list.appendChild(li);i++;}parent.appendChild(list);continue;}if(/^\s*>\s?/.test(line)){const quote=node('blockquote','markdown-quote'),parts=[];while(i<lines.length&&/^\s*>\s?/.test(lines[i]))parts.push(lines[i++].replace(/^\s*>\s?/,''));renderInline(quote,parts.join('\n'));parent.appendChild(quote);continue;}if(/^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line)){parent.appendChild(node('hr','markdown-rule'));i++;continue;}const parts=[line];i++;while(i<lines.length&&lines[i].trim()&&!/^(#{1,4})\s+/.test(lines[i])&&!/^\s*([-*+]\s+|\d+[.)]\s+|>\s?|```)/.test(lines[i])&&!(lines[i].includes('|')&&i+1<lines.length&&isTableDivider(lines[i+1])))parts.push(lines[i++]);const p=node('p','rich-line');parts.forEach((part,index)=>{if(index)p.appendChild(document.createElement('br'));renderInline(p,part);});parent.appendChild(p);}}
function selectTab(tab){if(!TABS[tab])return;state.tab=tab;for(const key of Object.keys(TABS))$(key+'-view').hidden=(key!==tab);document.querySelectorAll('.nav-item').forEach(n=>n.classList.toggle('selected',n.dataset.tab===tab));$('view-heading').textContent=TABS[tab];closeSidebar();if(tab==='defects')refreshDefects();}
function closeSidebar(){$('sidebar').classList.remove('mobile-open');$('overlay').hidden=true;}
function scrollBottom(){const box=$('chat-scroll');box.scrollTop=box.scrollHeight;}
function refreshQuestionOutline(){const list=$('question-outline-list'),outline=$('question-outline');if(!list||!outline)return;list.replaceChildren();const questions=[...$('messages').querySelectorAll('.message.user')];outline.hidden=questions.length===0;questions.forEach((row,index)=>{row.id=`conversation-question-${index+1}`;const text=(row.querySelector('.bubble')?.textContent||'').trim();const button=node('button','question-outline-item',`${index+1}. ${text}`);button.type='button';button.title=text;button.addEventListener('click',()=>row.scrollIntoView({behavior:'smooth',block:'start'}));list.appendChild(button);});}
function setQuestionOutlineCollapsed(collapsed){const outline=$('question-outline'),button=$('question-outline-toggle');outline.classList.toggle('collapsed',collapsed);button.textContent=collapsed?'‹':'›';button.setAttribute('aria-expanded',String(!collapsed));button.setAttribute('aria-label',collapsed?'展开提问目录':'收起提问目录');button.title=collapsed?'展开':'收起';localStorage.setItem('tripmind-question-outline-collapsed',collapsed?'1':'0');}
function fillAssistant(bubble,text,plan,trace,contextNote){bubble.replaceChildren();renderRichText(bubble,text);if(contextNote)bubble.appendChild(node("div","note",contextNote));if(plan)renderPlan(plan,bubble,true);if(Array.isArray(trace)&&trace.length){const detail=node('details','tool-trace'),summary=node('summary','',`工具调用记录 · ${trace.length} 次`);detail.appendChild(summary);for(const call of trace)detail.appendChild(node('p','note',`${call.status==='ok'?'✓':'!'} ${call.name} · ${call.status}`));bubble.appendChild(detail);}}
function renderMessage(role,text,plan,trace,contextNote){const row=node('article','message '+role);if(role==='assistant')row.appendChild(node('span','assistant-avatar','旅'));const bubble=node('div','bubble');if(role==='user')bubble.textContent=text;else fillAssistant(bubble,text,plan,trace,contextNote);row.appendChild(bubble);$('messages').appendChild(row);$('welcome').hidden=true;if(role==='user')refreshQuestionOutline();scrollBottom();return row;}
/* ---------------- 地图：优先高德 JS API，回退 Leaflet ---------------- */
function coordOf(spot,useWgs){return (useWgs&&spot&&spot.wgs_lat!=null&&spot.wgs_lon!=null)?[spot.wgs_lat,spot.wgs_lon]:[spot.lat,spot.lon];}

function loadAmapSdk(cfg){
  return new Promise(function(resolve){
    if(window.AMap)return resolve(true);
    if(!cfg||!cfg.key)return resolve(false);
    // 安全密钥必须在脚本加载前注入
    window._AMapSecurityConfig={securityJsCode:cfg.security_code||''};
    const s=document.createElement('script');
    s.src='https://webapi.amap.com/maps?v=2.0&key='+encodeURIComponent(cfg.key);
    s.onload=function(){resolve(Boolean(window.AMap));};
    s.onerror=function(){resolve(false);};
    document.head.appendChild(s);
  });
}

let amapConsoleHooked=false;
function hookAmapErrors(){
  if(amapConsoleHooked)return;
  amapConsoleHooked=true;
  const orig=console.error;
  console.error=function(){
    try{
      const text=Array.prototype.join.call(arguments,' ');
      if(/INVALID_USER_KEY|INVALID_USER_SCODE|INVALID_USER_DOMAIN|USERKEY/i.test(text)){
        window.__amapAuthError=String(text).slice(0,180);
      }
    }catch(err){}
    return orig.apply(console,arguments);
  };
}

function mapFallbackNote(text){
  const el=node('div','note',text);
  el.style.cssText='margin-top:8px;padding:8px 10px;background:#fff8ec;border:1px solid #f0dcc0;border-radius:8px;color:#8a6a3c';
  return el;
}

async function loadMapConfig(){
  try{state.mapConfig=await api('/api/map-config');}catch(err){state.mapConfig={provider:'none'};}
  if(state.mapConfig&&state.mapConfig.provider==='amap-js')await loadAmapSdk(state.mapConfig);
}

// 高德 JS API：坐标为 GCJ-02，与后端 lat/lon 完全一致，无需纠偏
// 按天配色：刻意拉开色相与明度差异，保证相邻两天在地图上不会看混
const DAY_COLORS=['#0e8a63','#2563eb','#ea580c','#9333ea','#db2777','#0891b2','#ca8a04'];
const DIM_OPACITY=0.45;

// 兼容两种入参：[[spot,...],...] 或 [{spots,legs},...]
function normalizeDays(input){
  const arr=Array.isArray(input)?input:(input?[input]:[]);
  return arr.map(function(item){
    if(Array.isArray(item))return {spots:item,legs:null};
    if(item&&Array.isArray(item.spots))return {spots:item.spots,legs:item.legs||null,day:item.day};
    return null;
  }).filter(function(d){return d&&d.spots&&d.spots.length;});
}

// 某一天的绘制段：优先用后端给的沿道路折线，缺失再退回直线
function dayPaths(day){
  const legs=(day.legs||[]).filter(function(l){return l&&Array.isArray(l.path)&&l.path.length>1;});
  if(legs.length)return legs.map(function(l){return {path:l.path,road:true};});
  if(day.spots.length>1)return [{path:day.spots.map(function(s){return [s.lon,s.lat];}),road:false}];
  return [];
}

function pinHtml(color,number,dimmed){
  return '<div class="route-pin" style="background:'+color+';opacity:'+(dimmed?'0.55':'1')+'">'
    +'<span>'+number+'</span></div>';
}

function drawAmap(host,days,intercity,onAuthFail){
  const map=new AMap.Map(host,{zoom:12,viewMode:'2D',resizeEnable:true});
  const dayLines=days.map(function(){return [];});
  const dayMarkers=days.map(function(){return [];});
  const dayMeta=days.map(function(day,di){
    return {color:DAY_COLORS[di%DAY_COLORS.length],markers:[]};
  });
  const all=[];
  let seq=0;

  days.forEach(function(day,di){
    const color=DAY_COLORS[di%DAY_COLORS.length];
    dayPaths(day).forEach(function(seg){
      const line=new AMap.Polyline({path:seg.path,strokeColor:color,
        strokeWeight:seg.road?5:3,strokeOpacity:seg.road?0.9:0.5,lineJoin:'round',
        strokeStyle:seg.road?'solid':'dashed'});
      dayLines[di].push(line); all.push(line);
    });
    (day.spots||[]).forEach(function(s){
      seq+=1;
      const marker=new AMap.Marker({
        position:[s.lon,s.lat],offset:new AMap.Pixel(-17,-17),title:s.name,
        content:pinHtml(color,seq,false)});
      marker.__pin={color:color,number:seq};
      dayMarkers[di].push(marker); all.push(marker);
    });
  });

  if(intercity&&intercity.start&&intercity.end){
    const ipath=(Array.isArray(intercity.polyline)&&intercity.polyline.length>1)
      ?intercity.polyline:[[intercity.start.lon,intercity.start.lat],[intercity.end.lon,intercity.end.lat]];
    all.push(new AMap.Polyline({path:ipath,strokeColor:'#9aa8a2',strokeWeight:3,
      strokeOpacity:0.85,strokeStyle:'dashed'}));
  }

  map.add(all);
  setTimeout(function(){map.setFitView(all.filter(function(o){return o instanceof AMap.Marker;}),false,[40,40,40,40],16);},150);

  // 侧栏切换：未选中的天压暗但保留，选中那天的线加粗并聚焦
  host.__focusDay=function(index){
    dayLines.forEach(function(lines,di){
      const active=(index==null||di===index);
      lines.forEach(function(line){
        line.setOptions({strokeOpacity:active?1:DIM_OPACITY,strokeWeight:active?6:3});
      });
    });
    dayMarkers.forEach(function(markers,di){
      const active=(index==null||di===index);
      markers.forEach(function(marker){
        const pin=marker.__pin||{};
        marker.setContent(pinHtml(pin.color,pin.number,!active));
        marker.setzIndex(active?200:100);
      });
    });
    const focus=(index==null)?[].concat.apply([],dayMarkers):(dayMarkers[index]||[]);
    if(focus.length)map.setFitView(focus,false,[40,40,40,40],16);
  };

  setTimeout(function(){
    if(window.__amapAuthError&&typeof onAuthFail==='function'){
      try{map.destroy();}catch(err){}
      host.replaceChildren();
      onAuthFail(window.__amapAuthError);
    }
  },3500);
}

// 开源底图回退：OSM 用纠偏后的 WGS-84，高德栅格用原始 GCJ-02
function drawLeaflet(host,days,intercity){
  const map=L.map(host,{scrollWheelZoom:false});
  const amap=L.tileLayer('https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',{subdomains:'1234',maxZoom:18,attribution:'&copy; 高德地图'});
  const osm=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'});
  amap.addTo(map);
  let useWgs=false;
  const dayLines=days.map(function(){return [];});
  const dayMarkers=days.map(function(){return [];});
  let seq=0;

  function toLatLng(lonLat){return [lonLat[1],lonLat[0]];}

  function build(){
    days.forEach(function(day,di){
      const color=DAY_COLORS[di%DAY_COLORS.length];
      const spots=day.spots||[];
      if(day.legs&&day.legs.some(function(l){return l&&Array.isArray(l.path)&&l.path.length>1;})){
        day.legs.forEach(function(l){
          if(!l||!Array.isArray(l.path)||l.path.length<2)return;
          dayLines[di].push(L.polyline(l.path.map(toLatLng),
            {color:color,weight:5,opacity:0.9,lineJoin:'round'}).addTo(map));
        });
      }else if(spots.length>1){
        dayLines[di].push(L.polyline(spots.map(function(s){return coordOf(s,useWgs);}),
          {color:color,weight:3,opacity:0.5,dashArray:'6 8',lineJoin:'round'}).addTo(map));
      }
      spots.forEach(function(s){
        seq+=1;
        const marker=L.marker(coordOf(s,useWgs),{icon:L.divIcon({
          className:'',html:pinHtml(color,seq,false),iconSize:[34,34],iconAnchor:[17,17]})})
          .bindTooltip(s.name,{direction:'top'}).addTo(map);
        marker.__pin={color:color,number:seq};
        dayMarkers[di].push(marker);
      });
    });
    if(intercity&&intercity.start&&intercity.end){
      const ipath=(Array.isArray(intercity.polyline)&&intercity.polyline.length>1)
        ?intercity.polyline.map(toLatLng)
        :[coordOf(intercity.start,useWgs),coordOf(intercity.end,useWgs)];
      L.polyline(ipath,{color:'#9aa8a2',weight:3,dashArray:'6 8'}).addTo(map);
    }
    const allPts=days.reduce(function(acc,d){return acc.concat((d.spots||[]).map(function(s){return coordOf(s,useWgs);}));},[]);
    if(allPts.length)map.fitBounds(L.latLngBounds(allPts).pad(0.18),{maxZoom:15});
  }

  function clearAll(){
    dayLines.forEach(function(lines){lines.forEach(function(l){map.removeLayer(l);});lines.length=0;});
    dayMarkers.forEach(function(markers){markers.forEach(function(m){map.removeLayer(m);});markers.length=0;});
    seq=0;
  }

  build();

  host.__focusDay=function(index){
    dayLines.forEach(function(lines,di){
      const active=(index==null||di===index);
      lines.forEach(function(line){
        line.setStyle({opacity:active?0.95:DIM_OPACITY,weight:active?6:3});
      });
    });
    dayMarkers.forEach(function(markers,di){
      const active=(index==null||di===index);
      markers.forEach(function(marker){
        const pin=marker.__pin||{};
        marker.setIcon(L.divIcon({className:'',html:pinHtml(pin.color,pin.number,!active),
          iconSize:[34,34],iconAnchor:[17,17]}));
        marker.setZIndexOffset(active?1000:0);
      });
    });
    const pts=(index==null)
      ?days.reduce(function(acc,d){return acc.concat((d.spots||[]).map(function(s){return coordOf(s,useWgs);}));},[])
      :(days[index].spots||[]).map(function(s){return coordOf(s,useWgs);});
    if(pts.length)map.fitBounds(L.latLngBounds(pts).pad(0.2),{maxZoom:16});
  };

  L.control.layers({'高德底图（GCJ-02 原始坐标）':amap,'OSM 底图（已纠偏到 WGS-84）':osm},{},{collapsed:false}).addTo(map);
  map.on('baselayerchange',function(e){
    useWgs=/OSM/.test(e.name);
    clearAll();
    build();
  });
  setTimeout(function(){map.invalidateSize();},150);
}

function dayHasRoad(day){
  return Array.isArray(day&&day.legs)&&day.legs.some(function(l){return l&&Array.isArray(l.path)&&l.path.length>1;});
}

function buildRouteMap(input,intercity){
  const days=normalizeDays(input);
  const spots=[].concat.apply([],days.map(function(d){return d.spots;}));
  const valid=spots.length>0&&spots.every(function(s){return s&&s.lat!=null&&s.lon!=null;});
  if(!valid)return routeSvg(spots);
  const host=node('div','route-map');
  setTimeout(function(){
    if(window.AMap&&state.mapConfig&&state.mapConfig.provider==='amap-js'){
      hookAmapErrors();
      try{
        drawAmap(host,days,intercity,function(reason){
          try{drawLeaflet(host,days,intercity);}catch(err){host.replaceChildren(routeSvg(spots));}
          const note=mapFallbackNote('高德 JS API 拒绝访问（'+reason+'），已自动切换到回退底图。'
            +'请检查：① key 的服务平台是否为「Web端(JS API)」；② 域名白名单是否含 127.0.0.1；'
            +'③ 是否在控制台生成并填写 AMAP_JS_SECURITY_CODE 安全密钥。');
          const parent=host.parentElement;
          if(parent&&!parent.querySelector('.map-fallback-note')){note.classList.add('map-fallback-note');parent.appendChild(note);}
        });
        return;
      }catch(err){/* 回落 */}
    }
    try{drawLeaflet(host,days,intercity);}catch(err){host.replaceChildren(routeSvg(spots));}
  },0);
  return host;
}

// 地图 + 按天侧栏
function buildDailyMapPanel(panel,days){
  const shell=node('div','map-with-days');
  const sidebar=node('div','map-day-list');
  const host=buildRouteMap(days,null);
  shell.appendChild(sidebar);
  shell.appendChild(host);

  const total=days.reduce(function(n,d){return n+(d.spots||[]).length;},0);
  function addItem(label,count,value,selected){
    const btn=node('button','map-day-item'+(selected?' selected':''));
    btn.type='button';
    const dot=node('span','map-day-dot');
    dot.style.background=value==null?'#9aa8a2':DAY_COLORS[value%DAY_COLORS.length];
    btn.appendChild(dot);
    btn.appendChild(node('span','map-day-label',label));
    if(value!=null){
      const day=days[value];
      if(day&&(day.spots||[]).length>1&&!dayHasRoad(day)){
        const badge=node('span','map-day-badge','直线');
        badge.title='这一天的路线未取得高德道路轨迹，按直线估算';
        btn.appendChild(badge);
      }
    }
    btn.appendChild(node('span','map-day-count',String(count)));
    btn.addEventListener('click',function(){
      sidebar.querySelectorAll('.map-day-item').forEach(function(b){b.classList.remove('selected');});
      btn.classList.add('selected');
      if(typeof host.__focusDay==='function')host.__focusDay(value);
    });
    sidebar.appendChild(btn);
  }
  addItem('全部路线',total,null,true);
  days.forEach(function(day,index){
    const count=(day.spots||[]).length;
    if(!count)return;
    addItem('第 '+(day.day||index+1)+' 天',count,index,false);
  });
  return shell;
}

/* 地图占位与「先算后画」：轨迹取完（或预算耗尽）才出图，避免直线→沿路闪一次 */
function mapPlaceholder(text){
  const el=node('div','route-map-skeleton',text||'正在计算路线…');
  el.style.cssText='height:380px;display:flex;align-items:center;justify-content:center;'
    +'color:#8b96a0;font-size:13px;background:#f8faf8;border:1px dashed #dfeae6;border-radius:12px';
  return el;
}

function routeSegments(days){
  const segs=[];
  days.forEach(function(day,di){
    const spots=day.spots||[];
    for(let i=1;i<spots.length;i++){
      segs.push({day:di,from:[spots[i-1].lon,spots[i-1].lat],to:[spots[i].lon,spots[i].lat]});
    }
  });
  return segs;
}

async function fillMaps(items){
  let note=null;
  const dailyItem=items.filter(function(i){return i.kind==='daily';})[0];
  if(dailyItem){
    const segs=routeSegments(dailyItem.days);
    if(segs.length){
      try{
        const data=await api('/api/route-geometry',{method:'POST',body:JSON.stringify({
          segments:segs.map(function(s){return {start:s.from,end:s.to};})})});
        if(data&&data.legs){
          const byDay={};
          data.legs.forEach(function(leg){
            const seg=segs[leg.index];
            if(!seg||!leg.path)return;
            (byDay[seg.day]=byDay[seg.day]||[]).push(leg.path);
          });
          Object.keys(byDay).forEach(function(key){
            dailyItem.days[key].legs=byDay[key].map(function(path){return {path:path,source:'walking'};});
          });
          note=data.note;
        }
      }catch(err){/* 拿不到就按直线出图，但只出一次 */}
    }
  }
  items.forEach(function(item){
    if(!item.panel.isConnected)return;
    const map=(item.kind==='daily')
      ? buildDailyMapPanel(item.panel,item.days)
      : buildRouteMap([{spots:[item.r.start,item.r.end]}],item.r);
    item.panel.replaceChildren(map);
    if(item.kind==='daily'&&note)item.panel.appendChild(node('div','note',note));
  });
}

function routeSvg(spots){const W=860,H=260,pad=45;const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('role','img');svg.setAttribute('aria-label','景点经纬度位置和连线示意图');if(!spots.length)return svg;
const minLat=Math.min(...spots.map(x=>x.lat)),maxLat=Math.max(...spots.map(x=>x.lat));const minLon=Math.min(...spots.map(x=>x.lon)),maxLon=Math.max(...spots.map(x=>x.lon));const dx=Math.max(.02,maxLon-minLon),dy=Math.max(.02,maxLat-minLat);
const px=s=>pad+((s.lon-minLon)/dx)*(W-2*pad),py=s=>H-pad-((s.lat-minLat)/dy)*(H-2*pad);
function shape(tag,attrs){const el=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>el.setAttribute(k,String(v)));svg.appendChild(el);return el;}
for(let i=0;i<5;i++)shape('line',{x1:25,x2:W-25,y1:20+i*54,y2:20+i*54,stroke:'#e0eae5','stroke-width':1,'stroke-dasharray':'4 6'});
if(spots.length>1)shape('polyline',{points:spots.map(s=>`${px(s)},${py(s)}`).join(' '),fill:'none',stroke:'#2a9c80','stroke-width':3.5,'stroke-linecap':'round','stroke-linejoin':'round'});
spots.forEach((s,i)=>{shape('circle',{cx:px(s),cy:py(s),r:11,fill:'#fff',stroke:'#168569','stroke-width':3});const t=shape('text',{x:px(s),y:py(s)-20,'text-anchor':'middle',fill:'#3d6660','font-size':11,'font-weight':600});t.textContent=`${i+1} ${s.name}`;const n=shape('text',{x:px(s),y:py(s)+4,'text-anchor':'middle',fill:'#16785e','font-size':10,'font-weight':700});n.textContent=String(i+1);});return svg;}
/* ---------------- 微调模式：本地调整，确认后一次重算 ---------------- */
const editState={active:false,draft:null,count:0};

function startEdit(){
  if(!state.currentPlan){toast('先规划一版行程');return;}
  editState.active=true;
  editState.draft=JSON.parse(JSON.stringify(state.currentPlan));
  editState.count=0;
  renderCurrentPlan();
  toast('已进入微调模式：点胶囊上的 × 移除，改完点「重新规划路线」');
}

function cancelEdit(){
  editState.active=false;editState.draft=null;editState.count=0;
  renderCurrentPlan();
  toast('已取消本次微调');
}

function removeSpotLocal(dayNumber,spot){
  const plan=editState.draft;
  const day=(plan.daily||[]).filter(function(d){return d.day===dayNumber;})[0];
  if(!day)return;
  day.spots=(day.spots||[]).filter(function(s){return s.id!==spot.id;});
  plan.unscheduled=plan.unscheduled||[];
  if(!plan.unscheduled.some(function(u){return u.name===spot.name;})){
    plan.unscheduled.unshift(Object.assign({},spot,{reason:'手动移除'}));
  }
  editState.count+=1;
  renderCurrentPlan();
}

function addSpotLocal(spot){
  const plan=editState.draft;
  let best=1,bestCount=Infinity;
  (plan.daily||[]).forEach(function(day){
    const count=(day.spots||[]).length;
    if(count<bestCount){bestCount=count;best=day.day;}
  });
  const day=(plan.daily||[]).filter(function(d){return d.day===best;})[0];
  if(!day)return;
  day.spots=(day.spots||[]).concat([spot]);
  plan.unscheduled=(plan.unscheduled||[]).filter(function(u){return u.name!==spot.name;});
  editState.count+=1;
  renderCurrentPlan();
  toast('已加入第 '+best+' 天（点「重新规划路线」生效）');
}

async function commitEdit(){
  if(!editState.count){toast('还没有调整内容');return;}
  const target=$('plan-result');
  try{
    const data=await api('/api/plan/reschedule',{method:'POST',
      body:JSON.stringify({plan:editState.draft}),timeout:90000});
    editState.active=false;editState.draft=null;editState.count=0;
    state.currentPlan=data;
    target.replaceChildren();
    renderPlan(data,target);
    toast('已按你的调整重新规划路线');
  }catch(err){toast('重新规划失败：'+err.message);}
}

function renderCurrentPlan(){
  const target=$('plan-result');
  if(!target)return;
  const plan=editState.active?editState.draft:state.currentPlan;
  if(!plan)return;
  target.replaceChildren();
  renderPlan(plan,target);
}

/* ---------------- 住宿地地图选点 ---------------- */
const lodgingPick={lat:null,lon:null,map:null,marker:null,mode:null};

function ensureLodgingModal(){
  let modal=document.getElementById('lodging-modal');
  if(modal)return modal;
  modal=node('div','modal-overlay');modal.id='lodging-modal';
  const card=node('div','modal-card');
  const head=node('div','modal-head');
  head.appendChild(node('h3','','在地图上选择住宿地'));
  const close=node('button','modal-close','×');close.type='button';
  close.addEventListener('click',closeLodgingPicker);head.appendChild(close);
  const host=node('div','lodging-map');host.id='lodging-map';
  const hint=node('p','note','点击地图选择位置，确认后会自动回填地址名。');
  hint.id='lodging-hint';
  const foot=node('div','modal-foot');
  const cancel=node('button','ghost-action','取消');cancel.type='button';
  cancel.addEventListener('click',closeLodgingPicker);
  const ok=node('button','primary-btn','使用这个位置');ok.type='button';
  ok.addEventListener('click',confirmLodgingPick);
  add(foot,cancel,ok);
  add(card,head,host,hint,foot);
  modal.appendChild(card);
  modal.addEventListener('click',function(e){if(e.target===modal)closeLodgingPicker();});
  document.body.appendChild(modal);
  return modal;
}

function openLodgingPicker(){
  ensureLodgingModal().classList.add('open');
  document.body.classList.add('modal-open');
  setTimeout(initLodgingMap,60);
}

function closeLodgingPicker(){
  const modal=document.getElementById('lodging-modal');
  if(modal)modal.classList.remove('open');
  document.body.classList.remove('modal-open');
}

function initLodgingMap(){
  const host=document.getElementById('lodging-map');
  if(!host)return;
  if(host.dataset.ready==='1'){if(lodgingPick.mode==='leaflet'&&lodgingPick.map)lodgingPick.map.invalidateSize();return;}
  host.dataset.ready='1';
  if(window.AMap&&state.mapConfig&&state.mapConfig.provider==='amap-js'){
    hookAmapErrors();
    lodgingPick.mode='amap';
    lodgingPick.map=new AMap.Map(host,{zoom:11,viewMode:'2D'});
    lodgingPick.map.on('click',function(e){setLodgingPoint(e.lnglat.getLng(),e.lnglat.getLat());});
    return;
  }
  lodgingPick.mode='leaflet';
  const map=L.map(host,{scrollWheelZoom:true});
  L.tileLayer('https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
    {subdomains:'1234',maxZoom:18,attribution:'&copy; 高德地图'}).addTo(map);
  map.setView([31.3,120.6],11);
  map.on('click',function(e){setLodgingPoint(e.latlng.lng,e.latlng.lat);});
  lodgingPick.map=map;
}

function setLodgingPoint(lon,lat){
  lodgingPick.lon=Number(lon);lodgingPick.lat=Number(lat);
  const hint=document.getElementById('lodging-hint');
  if(hint)hint.textContent='已选：'+Number(lon).toFixed(5)+', '+Number(lat).toFixed(5)+'（确认后回填地址名）';
  if(lodgingPick.mode==='amap'&&lodgingPick.map){
    if(lodgingPick.marker)lodgingPick.marker.setPosition([lon,lat]);
    else{lodgingPick.marker=new AMap.Marker({position:[lon,lat]});lodgingPick.map.add(lodgingPick.marker);}
    lodgingPick.map.setZoomAndCenter(14,[lon,lat]);
  }else if(lodgingPick.mode==='leaflet'&&lodgingPick.map){
    if(lodgingPick.marker)lodgingPick.marker.setLatLng([lat,lon]);
    else lodgingPick.marker=L.marker([lat,lon]).addTo(lodgingPick.map);
    lodgingPick.map.setView([lat,lon],14);
  }
}

async function confirmLodgingPick(){
  if(lodgingPick.lat==null||lodgingPick.lon==null){toast('请先在地图上点一个位置');return;}
  const input=$('lodging');
  const coordText=lodgingPick.lon.toFixed(5)+', '+lodgingPick.lat.toFixed(5);
  // 先落坐标并关闭弹窗，避免逆地理编码慢时界面像卡住
  input.value=coordText;
  closeLodgingPicker();
  toast('住宿地已设为：'+coordText+'（正在获取地址名）');
  try{
    const data=await api('/api/geocode/reverse?lon='+lodgingPick.lon+'&lat='+lodgingPick.lat);
    if(data.name&&document.getElementById('lodging').value===coordText){
      document.getElementById('lodging').value=data.name;
      toast('已回填地址：'+data.name);
    }
  }catch(err){/* 保留坐标即可 */}
}

window.__setLodgingPoint=setLodgingPoint;

/* ---------------- 保存/分享与微调 ---------------- */
async function saveItinerary(plan,container,button){
  button.disabled=true;
  try{
    const title=(plan.city||'')+' '+(plan.days||'')+' 天行程';
    const data=await api('/api/itineraries',{method:'POST',body:JSON.stringify({title:title,plan:plan})});
    const url=location.origin+data.url;
    const box=node('div','share-box');
    const input=node('input','share-input');input.value=url;input.readOnly=true;
    const copy=node('button','ghost-action','复制');copy.type='button';
    copy.addEventListener('click',function(){input.select();try{document.execCommand('copy');}catch(e){}toast('链接已复制');});
    add(box,input,copy,node('a','meta-link','打开'));box.lastChild.href=url;box.lastChild.target='_blank';
    container.appendChild(box);
  }catch(err){toast('保存失败：'+err.message);}
  finally{button.disabled=false;}
}

function opRemove(dayNumber,spotId){return {op:'remove',day:dayNumber,spot_id:spotId};}
function opAdd(dayNumber,spot){return {op:'add',day:dayNumber,spot:spot};}
function opAddBestDay(spot){
  const plan=state.currentPlan||{daily:[]};
  let best=1,bestCount=Infinity;
  (plan.daily||[]).forEach(function(day){
    const count=(day.spots||[]).length;
    if(count<bestCount){bestCount=count;best=day.day;}
  });
  return opAdd(best,spot);
}

async function editPlan(payload){
  const plan=state.currentPlan;
  if(!plan){toast('没有可编辑的行程');return;}
  const target=$('plan-result');
  try{
    const data=await api('/api/plan/edit',{method:'POST',body:JSON.stringify({plan:plan,...payload})});
    target.replaceChildren();
    renderPlan(data,target);
  }catch(err){toast('调整失败：'+err.message);}
}

async function loadSharedTrip(id){
  try{
    const data=await api('/api/itineraries/'+encodeURIComponent(id));
    selectTab('plan');
    const target=$('plan-result');
    target.replaceChildren();
    renderPlan(data.plan,target);
    toast('已载入分享的行程：'+data.title);
  }catch(err){toast('行程加载失败：'+err.message);}
}

function renderPlan(plan,target,compact=false){const wrap=node('section','result-wrap');const pendingMaps=[];const summary=node('div','plan-summary');add(summary,node('h2','',`${plan.origin} → ${plan.city} · ${plan.days} 天`),node('p','',`算法：${plan.clustering.toUpperCase()} + ${plan.routing.toUpperCase()}`+(plan.pace_label?` · ${plan.pace_label}节奏`:'')+` · ${plan.data_source}`));for(const [val,label] of [[plan.spot_count,'景点数'],[plan.total_distance_km+' km','直线距离合计'],[plan.cluster_count,'聚类簇数']]){const s=node('div','stat');add(s,node('strong','',String(val)),node('span','',label));summary.appendChild(s);}
state.currentPlan=plan;
const actions=node('div','plan-actions');
if(!editState.active){
  const saveBtn=node('button','ghost-action','保存并生成分享链接');saveBtn.type='button';
  saveBtn.addEventListener('click',function(){saveItinerary(plan,actions,saveBtn);});
  actions.appendChild(saveBtn);
  const editBtn=node('button','ghost-action ghost-strong','微调行程');editBtn.type='button';
  editBtn.addEventListener('click',startEdit);
  actions.appendChild(editBtn);
}else{
  const bar=node('div','edit-bar');
  bar.appendChild(node('span','edit-count','微调中：已调整 '+editState.count+' 项'));
  const commit=node('button','primary-btn edit-commit','重新规划路线');commit.type='button';
  commit.addEventListener('click',commitEdit);
  const cancel=node('button','ghost-action','取消');cancel.type='button';
  cancel.addEventListener('click',cancelEdit);
  bar.appendChild(commit);bar.appendChild(cancel);
  actions.appendChild(bar);
}
if(plan.lodging){actions.appendChild(node('span','note-inline','起点：'+(plan.lodging.name||'')));}
summary.appendChild(actions);
wrap.appendChild(summary);
const all=[];
for(const day of plan.daily){const card=node('section','day-card');add(card,node('h3','',`第 ${day.day} 天 · ${day.theme}`),node('div','day-meta',day.spots.length+' 个景点 · 游览 '+((day.day_load&&day.day_load.visit_hours)||day.duration_hours)+' 小时 · 交通 '+((day.day_load&&day.day_load.travel_hours)||0)+' 小时 · 余量 '+((day.day_load&&day.day_load.spare_hours)||0)+' 小时 · 直线约 '+day.distance_km+' km'));const chips=node('div','spot-list');for(const spot of day.spots){all.push(spot);const b=node('button','spot-pill',spot.name+' ↗');b.type='button';b.addEventListener('click',()=>{const old=card.querySelector('.spot-detail');if(old)old.remove();const detail=node('div','spot-detail');detail.style.cssText='margin-top:13px;padding:13px;background:#f8faf8;border-radius:10px;line-height:1.8';add(detail,node('strong','',spot.name),node('p','',spot.description||'暂无描述'),node('div','note',`建议游览 ${spot.duration_hours} 小时 · ${spot.tags.join(' / ')}`));if(spot.map_url){const a=node('a','meta-link','在高德地图查看 ↗');a.href=spot.map_url;a.target='_blank';a.rel='noopener noreferrer';detail.appendChild(a);}const removeBtn=node('button','ghost-action','从这个行程移除');removeBtn.type='button';
removeBtn.addEventListener('click',function(){editPlan(opRemove(day.day,spot.id));});
detail.appendChild(removeBtn);
if(spot.photo_url){const img=node('img');img.src=spot.photo_url;img.alt=spot.name;img.loading='lazy';img.style.cssText='max-width:100%;max-height:240px;object-fit:cover;border-radius:10px';img.onerror=()=>img.remove();detail.appendChild(img);if(spot.photo_credit){const source=node('a','meta-link',spot.photo_credit);source.href=spot.photo_source||spot.photo_url;source.target='_blank';source.rel='noopener noreferrer';detail.appendChild(source);}}else detail.appendChild(node('p','note','暂未收录该景点的授权实景照片，可在数据库 photo_url 字段补充。'));card.appendChild(detail);});if(editState.active){
  const wrap=node('span','pill-wrap');wrap.appendChild(b);
  const x=node('button','pill-x','×');x.type='button';x.title='从这一天移除（改完点「重新规划路线」）';
  x.addEventListener('click',function(ev){ev.stopPropagation();removeSpotLocal(day.day,spot);});
  wrap.appendChild(x);chips.appendChild(wrap);
}else{chips.appendChild(b);}}card.appendChild(chips);
if(!day.spots.length){card.appendChild(node('p','note','本日没有景点；可点上方「微调行程」，从「待安排」里把景点加回来。'));}
if(editState.active){const tip=node('p','edit-tip','点胶囊上的 × 移除；下方「待安排」里的景点可点 + 加回；改完点上方「重新规划路线」。');card.appendChild(tip);}if(Array.isArray(day.timeline)&&day.timeline.length){const tl=node('ol','day-timeline');day.timeline.forEach(function(item){const li=node('li','tl-item tl-'+item.kind);add(li,node('span','tl-time',item.start+'–'+item.end),node('span','tl-label',item.label));
if(item.warning){li.appendChild(node('span','tl-warn','⚠ '+item.warning));}tl.appendChild(li);});card.appendChild(tl);}wrap.appendChild(card);}
if(plan.unscheduled&&plan.unscheduled.length){const box=node('section','day-card unscheduled-card');box.appendChild(node('h3','','未排入的景点'));box.appendChild(node('div','day-meta',plan.capacity_note||'超出每日时间预算，建议增加天数'));const list=node('div','spot-list');plan.unscheduled.forEach(function(s){const btn=node('button','spot-pill','+ '+s.name);btn.type='button';
btn.title='加入行程（自动选当天景点最少的一天）';
btn.addEventListener('click',function(){if(editState.active)addSpotLocal(s);else editPlan(opAddBestDay(s));});
list.appendChild(btn);});box.appendChild(list);if(editState.active&&!plan.unscheduled.length){box.appendChild(node('p','note','待安排已清空，所有景点都在行程里了。'));}wrap.appendChild(box);}
if(plan.intercity_route){const r=plan.intercity_route;const card=node('section','day-card');add(card,node('h3','',`跨城市路线示意 · ${r.origin} → ${r.destination}`),node('div','day-meta',r.driving_distance_km!==undefined?`高德驾车 ${r.driving_distance_km} km · 估计 ${r.driving_duration_min} 分钟（不含实时路况）`:`两地直线距离约 ${r.straight_km} km，非高铁/驾车里程`));const panel=node('div','route-graphic');panel.appendChild(mapPlaceholder('正在计算跨城路线…'));card.appendChild(panel);wrap.appendChild(card);pendingMaps.push({panel:panel,kind:'intercity',r:r});}
if(all.length){const panel=node('div','route-graphic');panel.appendChild(mapPlaceholder('正在计算沿道路路线…'));wrap.appendChild(panel);pendingMaps.push({panel:panel,kind:'daily',days:plan.daily});}
if(!plan.intercity_route&&plan.intercity_note){wrap.appendChild(node('div','note',plan.intercity_note));}if(plan.capacity_note&&!(plan.unscheduled&&plan.unscheduled.length))wrap.appendChild(node('div','note',plan.capacity_note));if(plan.selection_note)wrap.appendChild(node('div','note',plan.selection_note));if(plan.route_note)wrap.appendChild(node('div','note',plan.route_note));wrap.appendChild(node('div','note',plan.map_note||plan.distance_note));if(compact)wrap.style.marginTop='20px';target.appendChild(wrap);if(pendingMaps.length)fillMaps(pendingMaps);
}
async function loadModels(){const data=await api('/api/models');state.models=data.models;const sel=$('model-picker');sel.replaceChildren();for(const item of data.models){const opt=node('option','',item.name+(item.configured?'':' · 未配置'));opt.value=item.id;sel.appendChild(opt);}state.model=data.default;sel.value=state.model;updateModelBadge();}
function updateModelBadge(){const model=state.models.find(x=>x.id===state.model);$('model-badge').textContent=model?.configured?'已配置':'需 API Key';$('model-badge').style.background=model?.configured?'#e9f6ef':'#fff1e5';$('model-badge').style.color=model?.configured?'#23886b':'#a66a35';}
async function loadCities(){/* V3 no destination whitelist: the user types any domestic city. */}
async function loadHistory(){const data=await api('/api/conversations');const box=$('history');box.replaceChildren();for(const c of data.conversations){const wrap=node('div','history-item'+(state.conversationId===c.id?' active':''));const b=node('button','history-open',c.title);b.title=c.title;b.addEventListener('click',()=>openConversation(c.id));const del=node('button','history-delete','×');del.title='删除对话';del.addEventListener('click',async()=>{if(!confirm('删除这段对话？'))return;try{await api('/api/conversations/'+encodeURIComponent(c.id),{method:'DELETE'});if(state.conversationId===c.id)resetChat();loadHistory();}catch(e){toast(e.message);}});add(wrap,b,del);box.appendChild(wrap);}}
function resetChat(){state.conversationId=null;$('messages').replaceChildren();$('welcome').hidden=false;$('send-button').disabled=false;refreshQuestionOutline();selectTab('chat');$('chat-input').focus();loadHistory().catch(e=>toast(e.message));}
function mountTask(task){renderMessage('user',task.message);const row=renderMessage('assistant',''),bubble=row.querySelector('.bubble'),status=node('div','thinking-status',task.statusText||'正在分析…');task.bubble=bubble;task.status=status;if(task.answer){fillAssistant(bubble,task.answer);bubble.classList.add('is-streaming');}bubble.appendChild(status);status.hidden=Boolean(task.answer);$('send-button').disabled=true;scrollBottom();}
function paintTask(task){if(state.conversationId!==task.id||!task.bubble?.isConnected)return;fillAssistant(task.bubble,task.answer);task.bubble.classList.toggle('is-streaming',!task.done);if(!task.done){task.status=node('div','thinking-status',task.statusText||'正在生成回答…');task.status.hidden=Boolean(task.answer);task.bubble.appendChild(task.status);}scrollBottom();}
async function openConversation(id){try{const data=await api('/api/conversations/'+encodeURIComponent(id));state.conversationId=id;$('messages').replaceChildren();for(const m of data.messages)renderMessage(m.role,m.content,m.meta?.plan,m.meta?.tool_trace,m.meta?.context_note);state.model=state.models.some(x=>x.id===data.model)?data.model:state.model;$('model-picker').value=state.model;updateModelBadge();const task=state.tasks.get(id);if(task)mountTask(task);else $('send-button').disabled=false;selectTab('chat');loadHistory();scrollBottom();}catch(e){toast(e.message);}}
async function sendChat(message){let conversationId=state.conversationId,task=null;if(conversationId&&state.tasks.has(conversationId))return;$('send-button').disabled=true;try{if(!conversationId){const created=await api('/api/conversations',{method:'POST',body:JSON.stringify({title:message.slice(0,36),model:state.model})});conversationId=created.id;state.conversationId=conversationId;loadHistory();}task={id:conversationId,message,answer:'',statusText:'正在分析…',done:false,bubble:null,status:null};state.tasks.set(conversationId,task);mountTask(task);const res=await fetch('/api/chat/stream',{method:'POST',headers:{'Content-Type':'application/json','Cache-Control':'no-cache'},body:JSON.stringify({message,model:state.model,conversation_id:conversationId}),cache:'no-store'});if(!res.ok){let detail=`HTTP ${res.status}`;try{const body=await res.json();detail=body.detail||detail;}catch(_){}throw Error(detail);}if(!res.body)throw Error('浏览器不支持流式响应');const reader=res.body.getReader(),decoder=new TextDecoder();let pending='',doneData=null;while(true){const part=await reader.read();if(part.done)break;pending+=decoder.decode(part.value,{stream:true});const lines=pending.split('\n');pending=lines.pop();for(const raw of lines){if(!raw.trim())continue;const event=JSON.parse(raw);if(event.event==='status'){task.statusText=event.text;if(task.status?.isConnected){task.status.textContent=event.text;task.status.hidden=false;}await new Promise(requestAnimationFrame);}else if(event.event==='delta'){task.answer+=event.text;paintTask(task);await new Promise(requestAnimationFrame);}else if(event.event==='done')doneData=event;else if(event.event==='error')throw Error(event.message);}}if(!doneData)throw Error('流式响应意外中断');task.done=true;if(state.conversationId===conversationId&&task.bubble?.isConnected){task.bubble.classList.remove('is-streaming');fillAssistant(task.bubble,task.answer,doneData.plan,doneData.tool_trace,doneData.context_note);$('send-button').disabled=false;}state.tasks.delete(conversationId);loadHistory();}catch(e){if(task){task.done=true;task.answer+=(task.answer?'\n\n':'')+'请求失败：'+e.message;paintTask(task);state.tasks.delete(conversationId);}if(state.conversationId===conversationId)$('send-button').disabled=false;toast(e.message);}finally{if(state.conversationId===conversationId&&!state.tasks.has(conversationId))$('send-button').disabled=false;scrollBottom();}}
/* ---------------- 候选景点：点胶囊即选中 ---------------- */
const poiState={city:'',spots:[],selected:new Set(),names:new Map()};
async function loadPoiCandidates(){
  const city=$('city-picker').value.trim();
  if(!city){toast('先填写目的地');return;}
  const status=$('poi-status');
  status.textContent='正在获取候选景点…';
  try{
    const data=await api('/api/pois?city='+encodeURIComponent(city));
    poiState.city=city;
    poiState.spots=data.spots||[];
    poiState.selected=new Set();
    renderPoiOptions();
    updatePoiCount(data.source==='amap_cache'?'（缓存）':'');
  }catch(err){
    poiState.spots=[];poiState.selected=new Set();renderPoiOptions();
    status.textContent=err.message;
  }
}
function renderPoiOptions(){
  const box=$('poi-options');
  if(!box)return;
  box.replaceChildren();
  poiState.spots.forEach(function(s){
    const btn=node('button','spot-pill'+(poiState.selected.has(s.id)?' selected':''),s.name);
    btn.type='button';
    btn.dataset.id=s.id;
    poiState.names.set(s.id,s.name);
    btn.title=(s.tags&&s.tags[0]?s.tags[0]+' · ':'')+'建议 '+(s.duration_hours||1.5)+' 小时';
    btn.addEventListener('click',function(){
      if(poiState.selected.has(s.id))poiState.selected.delete(s.id);
      else poiState.selected.add(s.id);
      btn.classList.toggle('selected',poiState.selected.has(s.id));
      updatePoiCount();
    });
    box.appendChild(btn);
  });
}
function updatePoiCount(prefix){
  const el=$('poi-status');
  if(!el||!poiState.spots.length)return;
  el.textContent=(prefix||'')+' '+(poiState.selected.size?('已选 '+poiState.selected.size+' / '):'')+poiState.spots.length+' 个候选';
}
const ROUTE_STYLES={balanced:['kmeans','dp'],compact:['dbscan','dp'],fast:['kmeans','greedy']};
function resolveRouteStyle(){
  const style=$('style-picker')?$('style-picker').value:'balanced';
  if(style==='custom')return {clustering:$('cluster-picker').value,routing:$('route-picker').value};
  const pair=ROUTE_STYLES[style]||ROUTE_STYLES.balanced;
  return {clustering:pair[0],routing:pair[1]};
}
function syncStyleControls(){
  const style=$('style-picker')?$('style-picker').value:'balanced';
  const custom=style==='custom';
  ['cluster-picker','route-picker'].forEach(function(id){const el=$(id);if(el)el.disabled=!custom;});
}
async function submitPlan(e){e.preventDefault();const target=$('plan-result');target.replaceChildren(node('div','empty-card','正在规划…'));const algo=resolveRouteStyle();try{const data=await api('/api/plan',{method:'POST',body:JSON.stringify({city:$('city-picker').value,origin:$('origin').value,days:Number($('days').value),clustering:algo.clustering,routing:algo.routing,pace:$('pace-picker')?$('pace-picker').value:'relaxed',day_start:($('day-start')&&$('day-start').value)?$('day-start').value:'09:00',
lodging:($('lodging')&&$('lodging').value)?$('lodging').value.trim():'',
lodging_lat:lodgingPick.lat,
lodging_lon:lodgingPick.lon,spot_ids:(poiState.city===$('city-picker').value.trim()?Array.from(poiState.selected):[]),spot_names:(poiState.city===$('city-picker').value.trim()?Array.from(poiState.selected).map(function(id){return poiState.names.get(id)||'';}).filter(Boolean):[])})});target.replaceChildren();renderPlan(data,target);}catch(err){target.replaceChildren(node('div','empty-card','生成失败：'+err.message));}}
async function submitBench(e){e.preventDefault();const root=$('bench-result');root.replaceChildren(node('div','empty-card','正在计算…'));try{const endpoint=$('bench-source').value==='fixture'?'/api/benchmark-fixture':'/api/benchmark';const data=await api(endpoint+'?'+new URLSearchParams({city:$('bench-city').value,days:$('bench-days').value}));const table=node('table','comparison-table');const head=node('tr');for(const h of ['聚类','路径优化','直线距离合计','簇数','噪声点'])head.appendChild(node('th','',h));table.appendChild(head);data.rows.forEach(row=>{const tr=node('tr');for(const val of [row.clustering,row.routing,row.distance_km+' km',row.cluster_count,row.noise_count])tr.appendChild(node('td','',String(val)));table.appendChild(tr);});root.replaceChildren(node('p','note','数据来源：'+(data.source||'未知')),table,node('p','note',data.note));}catch(err){root.replaceChildren(node('div','empty-card',err.message));}}
async function refreshDefects(){try{const [quality,result]=await Promise.all([api('/api/quality-summary'),api('/api/defects')]);const metrics=$('quality-metrics');metrics.replaceChildren();for(const [k,label] of [['total_defects','累计缺陷'],['open','待处理'],['fixed','已修复'],['verified','已复测']]){const box=node('div','metric');add(box,node('span','',label),node('strong','',String(k==='total_defects'?quality.total_defects:quality.by_status[k])));metrics.appendChild(box);}const list=$('defect-list');list.replaceChildren();if(!result.defects.length){list.appendChild(node('div','empty-card','暂无缺陷记录。请先执行真实测试，再如实登记。'));return;}
for(const d of result.defects){const card=node('div','defect-entry');const title=node('h3','',`#${d.id} ${d.title}`);title.appendChild(node('span','pill-tag',SEVERITIES[d.severity]||d.severity));add(card,title,node('p','',`复现步骤：${d.steps}`),node('p','',`预期：${d.expected}`),node('p','',`实际：${d.actual}`));const sel=node('select');for(const [v,label] of Object.entries(STATUSES)){const opt=node('option','',label);opt.value=v;sel.appendChild(opt);}sel.value=d.status;sel.addEventListener('change',async()=>{try{await api('/api/defects/'+d.id,{method:'PATCH',body:JSON.stringify({status:sel.value})});toast('缺陷状态已更新');refreshDefects();}catch(err){toast(err.message);sel.value=d.status;}});card.appendChild(sel);list.appendChild(card);}
}catch(err){toast(err.message);}}
async function submitDefect(e){e.preventDefault();const values={title:$('defect-title').value,steps:$('defect-steps').value,expected:$('defect-expected').value,actual:$('defect-actual').value,severity:$('defect-severity').value};try{await api('/api/defects',{method:'POST',body:JSON.stringify(values)});$('defect-form').reset();toast('缺陷已保存');refreshDefects();}catch(err){toast(err.message);}}
async function init(){document.querySelectorAll('[data-tab]').forEach(n=>n.addEventListener('click',()=>selectTab(n.dataset.tab)));$('new-chat').addEventListener('click',resetChat);$('refresh-history').addEventListener('click',()=>loadHistory().catch(e=>toast(e.message)));$('model-picker').addEventListener('change',e=>{state.model=e.target.value;updateModelBadge();});$('chat-form').addEventListener('submit',e=>{e.preventDefault();const message=$('chat-input').value.trim();if(!message)return;$('chat-input').value='';sendChat(message);});$('chat-input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('chat-form').requestSubmit();}});document.querySelectorAll('[data-prompt]').forEach(btn=>btn.addEventListener('click',()=>{$('chat-input').value=btn.dataset.prompt;$('chat-form').requestSubmit();}));$('plan-form').addEventListener('submit',submitPlan);$('bench-form').addEventListener('submit',submitBench);$('defect-form').addEventListener('submit',submitDefect);$('mobile-menu').addEventListener('click',()=>{$('sidebar').classList.add('mobile-open');$('overlay').hidden=false;});$('overlay').addEventListener('click',closeSidebar);
if($('style-picker')){$('style-picker').addEventListener('change',syncStyleControls);syncStyleControls();}
  if($('load-pois')){$('load-pois').addEventListener('click',loadPoiCandidates);}
  if($('pick-lodging')){$('pick-lodging').addEventListener('click',openLodgingPicker);}
  if($('lodging')){$('lodging').addEventListener('input',function(){lodgingPick.lat=null;lodgingPick.lon=null;});}
  const shared=new URLSearchParams(location.search).get('trip');
  if(shared){loadSharedTrip(shared);}
  if($('city-picker')){$('city-picker').addEventListener('input',function(){if(poiState.city&&poiState.city!==$('city-picker').value.trim()){poiState.spots=[];poiState.selected=new Set();poiState.city='';renderPoiOptions();const st=$('poi-status');if(st)st.textContent='目的地已修改，请重新获取候选';}});}
  try{await Promise.all([loadModels(),loadCities(),loadHistory(),loadMapConfig()]);await api('/api/health');$('server-dot').classList.add('ok');$('server-status').textContent='本地服务正常';}catch(err){$('server-status').textContent='连接失败';toast('初始化失败：'+err.message);}}
function initQuestionOutlineToggle(){setQuestionOutlineCollapsed(localStorage.getItem('tripmind-question-outline-collapsed')==='1');$('question-outline-toggle').addEventListener('click',()=>setQuestionOutlineCollapsed(!$('question-outline').classList.contains('collapsed')));}
window.addEventListener('DOMContentLoaded',initQuestionOutlineToggle);
window.addEventListener('DOMContentLoaded',init);
