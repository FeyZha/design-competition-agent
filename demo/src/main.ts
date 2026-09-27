import './style.css';
import { type CompetitionFeed, type CompetitionReport } from './types';
import { competitionDirections, competitionCreationTasks } from './competition-results';
import { scenarios } from './scenarios';
const $ = <T extends HTMLElement>(s:string) => document.querySelector<T>(s)!;
const text = (tag:string,value:string) => { const node=document.createElement(tag);node.textContent=value;return node; };
const safeURL = (value:string) => {try {const url=new URL(value);return ['http:','https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;} catch{return null;}};
let rows:CompetitionReport[]=[], tasks:CompetitionReport[]=[];
const dialog=$<HTMLDialogElement>('#detail'), choice=$<HTMLSelectElement>('#choice');
function submit(id:string){
 const scenario=scenarios.find(s=>s.id===id);if(!scenario)return;
 $('#welcome').hidden=true;$('#prompts').hidden=false;
 const turn=text('article','');turn.className='turn';
 const question=text('p',scenario.question);question.className='question';
 const answer=text('div','');answer.className='answer';
 const avatar=text('span','✦');avatar.className='avatar';avatar.setAttribute('aria-hidden','true');
 const content=text('div','');const label=text('p',scenario.label+' · 预制回复');label.className='eyebrow';
 content.append(label,text('p',scenario.reply));
 scenario.resultIds.forEach((id,i)=>{const r=rows.find(row=>row.id===id)!;const card=text('article','');card.className='card';
 const number=text('span',String(i+1).padStart(2,'0'));number.className='number';
 const tags=text('p',`${r.designTypes?.join(' / ')||'方向待整理'} · 截止 ${r.deadline||'待确认'}`);tags.className='eyebrow';
 const title=text('h3',r.displayTitle||r.competitionTitle||r.title);const description=text('p',r.themeTask||'主题待明确');description.className='description';
 const button=text('button','查看规则与任务书 ↗');button.setAttribute('aria-haspopup','dialog');button.onclick=()=>open(r);
 card.append(number,tags,title,description,button);content.append(card);});
 answer.append(avatar,content);turn.append(question,answer);$('#turns').append(turn);
 $('#conversation').scrollTo({top:turn.offsetTop-$('#conversation').offsetTop,behavior:'smooth'});
}
for(const container of [$('#suggestions'),$('#prompts')]){
 scenarios.forEach((s,i)=>{const button=text('button',`${container.id==='suggestions'?'0'+(i+1)+'  ':''}${s.question}`) as HTMLButtonElement;button.disabled=true;button.onclick=()=>submit(s.id);container.append(button);});
}
$('#new-chat').onclick=()=>{$('#turns').replaceChildren();$('#welcome').hidden=false;$('#prompts').hidden=true;$('#conversation').scrollTop=0;};
function open(row:CompetitionReport){
 $('#detail-title').textContent=row.displayTitle||row.competitionTitle||row.title;const body=$('#detail-body');body.replaceChildren();
 const sections=[['参赛资格',row.eligibility],['截止日期',row.deadline],['费用',row.fee],['AI 使用规则',row.aiRule],['创作主题',row.themeTask],['交付内容',row.submissionFormat],['绑定依据',row.bindingEvidence?.quote],['待确认信息',[row.pendingReason,...row.missingInformation||[]].filter(Boolean).join('；')]];
 for(const [title,value] of sections){if(!value)continue;body.append(text('h3',title!),text('p',value));}
 for(const evidence of row.evidence||[]){const quote=text('blockquote',evidence.quote);body.append(quote);}
 const url=safeURL(row.sourceUrl);if(url){const link=text('a','查看原始规则 ↗') as HTMLAnchorElement;link.href=url;link.target='_blank';link.rel='noreferrer';body.append(link);}
 tasks=competitionCreationTasks(row);choice.replaceChildren(...tasks.map((task,i)=>new Option(task.creationCategory||task.title,String(i))));$('#choice-label').hidden=tasks.length<2;
 $('#download-status').textContent='';($<HTMLButtonElement>('#download')).disabled=!tasks.length;dialog.showModal();
}
$('#close').onclick=()=>dialog.close();
$('#download').onclick=()=>{const task=tasks[Number(choice.value)||0];if(!task)return;const value=`# ${task.displayTitle||task.title}\n\n> 历史快照任务书，请向官方核实当前规则。\n\n## 创作主题\n${task.themeTask}\n\n## 交付要求\n${task.submissionFormat}\n\n## 资格\n${task.eligibility}\n\n## 费用\n${task.fee}\n\n## AI 规则\n${task.aiRule}\n\n## 来源\n${safeURL(task.sourceUrl)||'待确认'}\n`;const url=URL.createObjectURL(new Blob([value],{type:'text/markdown;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download='competition-brief.md';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$('#download-status').textContent='已下载任务书，保留完整交付要求与来源。';};
fetch('/feed.json').then(async response=>{
 if(!response.ok)throw new Error('数据读取失败');const feed=await response.json() as CompetitionFeed;rows=competitionDirections(feed);
 if(scenarios.some(s=>s.resultIds.some(id=>!rows.some(r=>r.id===id))))throw new Error('预制场景资料缺失');
 $('#snapshot').textContent=`${feed.items.length} 条已保存赛事 · ${feed.fetchedAt?.slice(0,10)||'历史'} 快照`;
 document.querySelectorAll<HTMLButtonElement>('#suggestions button,#prompts button').forEach(b=>b.disabled=false);
}).catch(()=>{$('#snapshot').textContent='暂时无法读取预制数据，请刷新重试。';});
