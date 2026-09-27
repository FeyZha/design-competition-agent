import './style.css';
import { DESIGN_DIRECTIONS, type CompetitionFeed, type CompetitionReport } from './types';
import { competitionDirections, competitionCreationTasks } from './competition-results';
const $ = <T extends HTMLElement>(s:string) => document.querySelector<T>(s)!;
const text = (tag:string,value:string) => { const node=document.createElement(tag);node.textContent=value;return node; };
const safeURL = (value:string) => {try {const url=new URL(value);return ['http:','https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;} catch{return null;}};
let rows:CompetitionReport[]=[], scenario='all', tasks:CompetitionReport[]=[];
const type=$<HTMLSelectElement>('#type'), search=$<HTMLInputElement>('#search'), ai=$<HTMLInputElement>('#ai'), dialog=$<HTMLDialogElement>('#detail'), choice=$<HTMLSelectElement>('#choice');
DESIGN_DIRECTIONS.forEach(value=>type.add(new Option(value,value)));
function render(){
 const query=search.value.trim().toLowerCase();
 const matches=rows.filter(r=>scenario!=='empty' && (scenario!=='bound' || Boolean(r.bindingEvidence?.quote)) && (!type.value || r.designTypes?.includes(type.value as never)) && (!ai.checked || r.aiAllowed===true) && (!query || [r.title,r.competitionTitle,r.themeTask].join(' ').toLowerCase().includes(query)));
 $('#count').textContent=`${matches.length} 个方向`;
 const list=$('#list');list.replaceChildren();
 if(!matches.length){list.append(text('h3','没有符合条件的方向'),text('p','这份快照中没有匹配结果。可以切换测试场景或调整筛选条件。'));return;}
 matches.forEach((r,i)=>{const card=document.createElement('article');card.className='card';const number=text('span',String(i+1).padStart(2,'0'));number.className='number';const content=document.createElement('div');
 const tags=text('p',`${r.designTypes?.join(' / ')||'方向待整理'} · ${r.deadline||'截止时间待确认'}`);tags.className='eyebrow';const title=text('h3',r.displayTitle||r.competitionTitle||r.title);const description=text('p',r.themeTask||'主题待明确');description.className='description';const button=text('button','查看规则与任务书 ↗');button.onclick=()=>open(r);content.append(tags,title,description,button);card.append(number,content);list.append(card);});
}
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
$('#scenarios').onclick=e=>{const button=(e.target as HTMLElement).closest<HTMLButtonElement>('button[data-scenario]');if(!button)return;scenario=button.dataset.scenario!;type.value=scenario==='poster'?'海报':'';search.value='';ai.checked=false;document.querySelectorAll<HTMLButtonElement>('[data-scenario]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();};
for(const control of [search,type,ai])control.addEventListener('input',render);
fetch('/feed.json').then(async response=>{if(!response.ok)throw new Error('数据读取失败');const feed=await response.json() as CompetitionFeed;rows=competitionDirections(feed);$('#snapshot').textContent=`${feed.items.length} 条已保存赛事 · ${feed.fetchedAt?.slice(0,10)||'历史'}快照`;render();}).catch(()=>{$('#list').replaceChildren(text('p','暂时无法读取预制数据，请刷新重试。'));});
