/* Claude Mods compatibility runtime. No DOM, Node or ambient filesystem. */
var __hooks = [], __queue = [], __waiters = {}, __results = {}, __counter = 0;
var __modules = {}, __cache = {}, __commands = [], __tools = [], __state = {}, __panes = [];
var __actions = {}, __actionCounter = 0, __atomCounter = 0, __options = {}, __info = {}, __current = {}, __hasContinuation = false;
function __bridge(method, args) {
  const id = String(++__counter);
  return new Promise((resolve,reject)=>{ __waiters[id]={resolve,reject}; __queue.push({id,method,args}); });
}
function __settle(id, value, error) { const p=__waiters[id]; if (!p) return; delete __waiters[id]; error ? p.reject(new Error(error)) : p.resolve(value); }
function __drain() { const q=__queue; __queue=[]; return JSON.stringify(q); }
function __match(filter,e) {
  return !filter || Object.entries(filter).every(([key,want])=> {
    if(want==='*') return true;
    if(typeof want==='string' && want.includes('*')) return new RegExp('^'+want.split('*').map(s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('.*')+'$').test(String(e[key]||''));
    return e[key]===want;
  });
}
function on(event, filter, handler) {
  if(typeof filter==='function') { handler=filter; filter=null; }
  const entry={event,filter,handler}; __hooks.push(entry);
  return {catch(fn) { entry.errorHandler=fn; }};
}
function __element(type,props) {
  props={...(props||{})};
  for(const key of ['onPress','onInput','onSubmit','onSelect','onChange']) {
    if(typeof props[key]==='function') { const id='a'+(++__actionCounter); __actions[id]=props[key]; props[key]=id; const keys=Object.keys(__actions);if(keys.length>4096)delete __actions[keys[0]]; }
  }
  return {type,props,children:props.children||[]};
}
function h(type,props,...children) {
  props={...(props||{}),children:children.flat(Infinity)};
  return typeof type==='function'?type(props):__element(type||'Box',props);
}
function Fragment(props){return __element('Box',props);}
var __elements = Object.fromEntries(['Box','Text','Button','Link','Code','Markdown','Input','Select','Checkbox','Switch','Separator','Badge','Progress','Svg','Client','Image'].map(k=>[k,p=>__element(k,p)]));
var __atoms={};
var __claude = {
  atom: value=>({__atom:true,key:'atom'+(++__atomCounter),initial:value}),
  read: value=>value&&value.__atom?(__atoms[value.key]??value.initial):value,
  update: (atom,fn)=>{__atoms[atom.key]=fn(__atoms[atom.key]??atom.initial);},
  derive: fn=>fn, memberOf: (obj,key)=>({obj,key}),
};
var $ = {
  plugin:{ get name(){return __info.name;}, root:'.' },
  store:{get:key=>__bridge('storage.get',{key}), set:(key,value)=>__bridge('storage.set',{key,value}), delete:key=>__bridge('storage.delete',{key}), keys:(prefix='')=>__bridge('storage.keys',{prefix})},
  state:{get:key=>typeof key==='object'?__claude.read(key):__state[key], set:(key,value)=>{ if(typeof key==='object')__atoms[key.key]=value;else __state[key]=value; }},
  fs:{read:path=>__bridge('files.read',{name:typeof path==='string'?path:path.path}),write:(path,text)=>__bridge('files.write',{name:path,text}),list:(path='')=>__bridge('files.list',{name:path}), exists:async path=>{try{await $.fs.read(path);return true;}catch{return false;}}},
  http:{fetch:async(url,init={})=>{const r=await __bridge('http.request',{method:init.method||'GET',url,headers:init.headers,body:init.body});return {...r,text:async()=>r.text,json:async()=>r.json};}},
  ui:{resolve:()=>__elements,invalidate:()=>{__queue.push({id:'',method:'compat.ui',args:{event:'ui.invalidate',data:{}}});},panes:()=>__panes,open:async pane=>{__panes=__panes.filter(p=>p.id!==pane.id);__panes.push(pane);return {id:pane.id,isPlaced:true};},close:async pane=>{__panes=__panes.filter(p=>p.id!==pane.id);},
    toast:(text)=>__bridge('compat.ui',{event:'ui.toast',data:{text}}),status:text=>__bridge('compat.ui',{event:'ui.status',data:{text}}),log:text=>__bridge('log',{message:String(text)}),notice:text=>__bridge('log',{message:String(text)})},
  tool:{register:async spec=>{__tools.push(spec);return {tool:'mcp__'+__info.name+'__'+spec.name};},list:()=>__bridge('compat.tools',{}),call:args=>__bridge('compat.tool.call',args)},
  command:{register:async spec=>{__commands=__commands.filter(command=>command.name!==spec.name);__commands.push(spec);return {command:spec.name};},list:async()=>__commands,run:args=>__dispatch('command.run',args)},
  prompt:{read:async()=>({text:__current.text||''}),compose:async()=>({sections:__current.sections||[]}), fill:text=>__bridge('compat.ui',{event:'assistant.fill',data:{text:typeof text==='string'?text:text.text}})},
  session:{id:()=>__current.sessionId||null,model:()=>__current.model||null,messages:async()=>__current.messages||[],usage:()=>__bridge('compat.session.usage',{}),surfaces:()=>['desktop'],version:()=> 'openfic-compat/2.0.0',cwd:()=>__current.projectId?'openfic://projects/'+encodeURIComponent(__current.projectId):'.',root:()=>'.'},
  model:{complete:args=>__bridge('models.complete',{messages:args.messages||[{role:'user',content:args.prompt||args.text||''}],model_id:args.model})},
  clock:{now:()=>Date.now(),sleep:ms=>__bridge('compat.sleep',{ms})},
  config:{list:async()=>Object.entries(__options).map(([key,value])=>({key,value})),set:async({key,value})=>{__options[key]=value;return {value};}},
  settings:{read:async()=>__options},
  env:{get:()=>undefined},
};
var console = {log:(...args)=>{__queue.push({id:'',method:'log',args:{message:args.map(String).join(' ')}});},error:(...args)=>console.log(...args),warn:(...args)=>console.log(...args)};
async function __dispatch(name,data) {
  __current=data;
  const list=__hooks.filter(x=>(x.event===name||x.event==='*')&&__match(x.filter,data));
  async function step(i,e) {
    if(i===list.length) return __hasContinuation ? await __bridge('compat.next',e) : e;
    const entry=list[i];let called=false;
    const next=value=>{if(called)throw new Error('next called twice');called=true;const promise=step(i+1,value===undefined?e:value);promise[Symbol.asyncIterator]=async function*(){yield await promise;};return promise;};
    next.signal={aborted:false,throwIfAborted(){}};next.origin={plugin:'engine',tier:'core'};
    next.budget={ms:30000,remainingMs:30000};
    try {
      const result=entry.handler($,e,next);
      if(result&&result[Symbol.asyncIterator]){let value;for await(const item of result)value=item;return value===undefined?e:value;}
      return await result;
    }
    catch(error){if(!entry.errorHandler)throw error;next.error={kind:'throw',message:String(error)};next.called=called;return await entry.errorHandler($,e,next);}
  }
  return await step(0,data);
}
async function __action(id,value){if(!__actions[id])throw new Error('UI action expired');return await __actions[id](value,{value});}
function __begin(id,kind,data){Promise.resolve(kind==='action'?__action(data.id,data.value):__dispatch(kind,data)).then(value=>__results[id]={done:true,value:value===undefined?null:value},error=>__results[id]={done:true,error:String(error)});}
function __take(id){const r=__results[id];if(r)delete __results[id];return JSON.stringify(r||null);}
function __require(name,from='') {
  if(name==='claude-code')return __claude;
  if(name==='react')return {createElement:h,Fragment};
  if(!name.startsWith('.'))throw new Error('Unsupported module: '+name);
  const parts=from.split('/').slice(0,-1);
  for(const p of name.split('/')){if(p==='..')parts.pop();else if(p&&p!=='.')parts.push(p);}
  const key=parts.join('/');
  const filename=[key,key+'.js',key+'.ts',key+'.tsx',key+'.jsx',key+'.mjs',key+'.mts',key+'.cts',key+'.json',key+'/index.js',key+'/index.ts',key+'/index.tsx'].find(k=>__modules[k]);
  if(!filename)throw new Error('Module not found: '+key);
  if(__cache[filename])return __cache[filename].exports;
  const module={exports:{}};__cache[filename]=module;
  __modules[filename](module,module.exports,s=>__require(s,filename));return module.exports;
}
