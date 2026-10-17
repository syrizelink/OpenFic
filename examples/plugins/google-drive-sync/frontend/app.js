const $=id=>document.getElementById(id);let context;let busy=false;
function message(value){$('status').textContent=value;}
async function connection(){const data=await OpenFic.call('drive.status',{projectId:$('project').value});$('connection').textContent=data.connected?'已连接':'尚未连接';}
async function perform(dryRun=false,resolutions={}){
 if(busy)return;busy=true;for(const b of document.querySelectorAll('button'))b.disabled=true;
 message('正在比较本地与云端章节…');
 try{const report=await OpenFic.call('drive.sync',{projectId:$('project').value,mode:$('mode').value,dryRun,resolutions});message(report.dryRun?'变化预览完成，未修改内容':'同步完成');
 $('report').textContent=`上传 ${report.uploaded} · 下载 ${report.downloaded} · 导入 ${report.imported} · 无变化 ${report.unchanged} · 待同步 ${report.pending} · 冲突 ${report.conflicts.length}`;
 $('conflicts').replaceChildren();for(const c of report.conflicts){const row=document.createElement('div');row.className='conflict';const text=document.createElement('p');text.textContent=c.title+'：本地与云端均有修改';row.append(text);for(const [value,label] of [['local','使用本地版本'],['remote','使用云端版本']]){const button=document.createElement('button');button.textContent=label;button.onclick=async()=>{if(await OpenFic.ui.confirm('确认以所选版本覆盖另一端的这一章？'))await perform(false,{[c.chapterId]:value});};row.append(button);}$('conflicts').append(row);}
 }catch(e){message(e.message);}finally{busy=false;for(const b of document.querySelectorAll('button'))b.disabled=false;}
}
$('sync').onclick=()=>perform();$('preview').onclick=()=>perform(true);$('project').onchange=connection;
$('connect').onclick=async()=>{try{const result=await OpenFic.call('drive.connect');$('redirect').textContent='OAuth 控制台需登记的 Redirect URI：'+result.redirect_uri;await OpenFic.ui.openExternal(result.url);message('请在授权页面完成连接，然后返回本页。');}catch(e){message(e.message);}};
$('disconnect').onclick=async()=>{try{await OpenFic.call('drive.disconnect');await connection();}catch(e){message(e.message);}};
$('save-token').onclick=async()=>{try{const value=$('token').value.trim();if(!value)throw new Error('请输入令牌');await OpenFic.secrets.set('oauth.tokens',{access_token:value,obtained_at:Date.now()/1000,expires_in:3600});$('token').value='';await connection();message('令牌已加密保存');}catch(e){message(e.message);}};
OpenFic.on('oauth.connected',()=>connection());
OpenFic.ready.then(async c=>{context=c;try{const projects=await OpenFic.data.projects();for(const p of projects){const option=document.createElement('option');option.value=p.id;option.textContent=p.title;$('project').append(option);}if(c.projectId)$('project').value=c.projectId;await connection();}catch(e){message(e.message);}});
