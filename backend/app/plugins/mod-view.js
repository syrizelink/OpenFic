let current;
const status=document.getElementById('status');
function draw(node){
 if(node==null||node===false)return document.createTextNode('');
 if(Array.isArray(node)){const box=document.createElement('div');node.forEach(n=>box.append(draw(n)));return box;}
 if(typeof node!=='object')return document.createTextNode(String(node));
 const props=node.props||{},type=node.type||node.tag||'Box';
 if(!node.type&&node.props){return document.createTextNode(JSON.stringify(props));}
 if(!node.type&&!node.tag)return document.createTextNode(node.text||node.suffix||'');
 const tag={Text:'span',Box:'div',Button:'button',Input:'input',Select:'select',Code:'pre',Markdown:'pre',Link:'a'}[type]||'div';
 const el=document.createElement(tag);
 if(type==='Button'){el.textContent=props.label||'Run';el.onclick=()=>runAction(props.onPress);}
 else if(type==='Input'){el.placeholder=props.placeholder||'';el.value=props.value||'';el.onchange=()=>runAction(props.onInput||props.onSubmit,el.value);}
 else if(type==='Select'){for(const o of props.options||[]){const op=document.createElement('option');op.value=o.value;op.textContent=o.label||o.value;el.append(op);}el.value=props.value||'';el.onchange=()=>runAction(props.onSelect,el.value);}
 else if(type==='Link'){try{const url=new URL(props.href);if(['https:','http:'].includes(url.protocol)){el.href=url.href;el.target='_blank';el.rel='noopener noreferrer';}}catch{}el.textContent=props.label||props.href;}
 else if(props.text||props.source)el.textContent=props.text||props.source;
 else for(const child of [node.children||props.children||[]].flat())el.append(draw(child));
 if(props.bold)el.style.fontWeight='bold';
 if(type==='Box'){el.style.display='flex';el.style.flexDirection=props.flexDirection||'column';el.style.gap='6px';}
 if(type==='Client')el.textContent='Client renderer modules are not supported by this host.';
 return el;
}
async function runAction(id,value){if(!id)return;try{await OpenFic.call('mod.action',{id,value});await refresh();}catch(e){status.textContent=e.message;}}
async function refresh(){
 const result=await OpenFic.call('mod.inspect');current=result;
 status.textContent=(result.compatibility.warnings||[]).join('\n');
 const commands=document.getElementById('commands');commands.replaceChildren();
 for(const cmd of result.commands){const button=document.createElement('button');button.textContent='/'+cmd.name;button.onclick=async()=>{try{const r=await OpenFic.call('mod.command',{command:cmd.name,args:''});status.textContent=r?.text||JSON.stringify(r);await renderTrees();}catch(e){status.textContent=e.message;}};commands.append(button);}
 await renderTrees();
}
async function renderTrees(){const result=await OpenFic.call('mod.inspect');document.getElementById('render').replaceChildren(...result.trees.map(t=>draw(t.tree)));}
OpenFic.ready.then(async c=>{document.getElementById('title').textContent=c.pluginId;try{await refresh();}catch(e){status.textContent=e.message;}});
