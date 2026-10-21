"""Read-only presentation helpers. No event mutation or inference."""
import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from streamlit_echarts import st_echarts

TZ=timezone(timedelta(hours=8))
def esc(value):return html.escape(str(value),quote=True)
def local_time(value):
    try:
        d=datetime.fromisoformat(value)
        return d.replace(tzinfo=timezone.utc).astimezone(TZ) if d.tzinfo is None else d.astimezone(TZ)
    except (ValueError,TypeError):return None
def title(value):st.markdown(f'<div class="panel-title">{esc(value)}</div>',unsafe_allow_html=True)
def header():
    st.markdown('<div class="command-header"><small>校园安全 · 视觉辅助监测</small><h1>棚安 · 车棚火情智能监测与接警处置系统</h1></div><div class="simulation">● 视频演示模式　｜　短信仅模拟发送，不会发送至手机　｜　当前未接入实时摄像头</div>',unsafe_allow_html=True)
    components.html("""<style>body{margin:0;background:#0a1628;color:#7a9cc6;font:12px sans-serif;text-align:right}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#54e4a0;margin:0 8px;animation:p 2s infinite}@keyframes p{50%{box-shadow:0 0 8px #54e4a0}}@media(prefers-reduced-motion:reduce){.dot{animation:none}}</style><span id="clock"></span><span class="dot"></span>页面已加载<script>function tick(){document.getElementById('clock').textContent=new Date().toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})+' 北京时间'}tick();setInterval(tick,1000)</script>""",height=24)
def log_data(root):
    today=datetime.now(TZ).date();frames=0;entries=[];skipped=0
    for path in (root/'runs').glob('*/config.json'):
        try:
            cfg=json.loads(path.read_text(encoding='utf-8'))
            result=json.loads((path.parent/'result.json').read_text(encoding='utf-8'))
            when=local_time(cfg.get('created_at'))
            if when and when.date()==today:frames+=int(result.get('samples',0))
            entries.append((when,cfg,result))
        except (OSError,ValueError,TypeError):skipped+=1
    entries.sort(key=lambda r:r[0] or datetime.min.replace(tzinfo=TZ),reverse=True)
    return frames,entries,skipped
def dashboard(store,rows):
    frames,runs,skipped=log_data(store.root)
    sites=sorted({r.get('site','未填写') for r in rows})
    left,center,right=st.columns([1,2,1],gap='medium')
    with left:
        with st.container(border=True,key="panel_metrics"):
            title('监测概览')
            values=[frames,len(rows),len(sites)]
            labels=['今日已汇总采样帧','累计告警事件','已记录地点']
            cards=''.join(f'<div class="metric"><b data-v="{v}">{v}</b><span>{label}</span></div>' for v,label in zip(values,labels))
            components.html(f"""<style>body{{margin:0;font-family:sans-serif}}.row{{display:flex;gap:6px}}.metric{{flex:1;text-align:center;background:#10284a;border-top:2px solid #00d4ff;padding:14px 3px}}b{{display:block;color:#00d4ff;font-size:25px}}span{{color:#9cb7da;font-size:11px}}</style><div class="row">{cards}</div><script>if(!matchMedia('(prefers-reduced-motion: reduce)').matches){{document.querySelectorAll('b').forEach(e=>{{let v=+e.dataset.v,t=performance.now();function f(n){{let k=Math.min(1,(n-t)/650);e.textContent=Math.round(v*k);if(k<1)requestAnimationFrame(f)}}requestAnimationFrame(f)}})}}</script>""",height=110)
            st.caption('采样帧按北京时间汇总已有分析结果，不含未保存的处理中帧。')
        with st.container(border=True,key="panel_charts"):
            title('事件处置分布')
            data=[dict(name=k,value=sum(r['status']==k for r in rows)) for k in ['待接警','处理中','已结案']]
            if rows:
                st_echarts({'backgroundColor':'transparent','color':['#ff6b35','#00d4ff','#54e4a0'],'tooltip':{'trigger':'item'},'legend':{'bottom':0,'textStyle':{'color':'#9cb7da'}},'series':[{'type':'pie','radius':['48%','70%'],'center':['50%','43%'],'label':{'show':False},'data':data}]},height='220px',key='state_donut')
            else:st.caption('暂无事件，等待视频分析。')
            title('近7日新增事件')
            days=[datetime.now(TZ).date()-timedelta(days=i) for i in range(6,-1,-1)]
            counts=[sum(bool(local_time(r.get('created_at'))) and local_time(r['created_at']).date()==d for r in rows) for d in days]
            st_echarts({'backgroundColor':'transparent','tooltip':{'trigger':'axis'},'grid':{'left':28,'right':10,'top':20,'bottom':30},'xAxis':{'type':'category','data':[d.strftime('%m-%d') for d in days],'axisLabel':{'color':'#7a9cc6','fontSize':10}},'yAxis':{'type':'value','minInterval':1,'axisLabel':{'color':'#7a9cc6'},'splitLine':{'lineStyle':{'color':'#1e90ff20'}}},'series':[{'type':'bar','data':counts,'barMaxWidth':20,'itemStyle':{'color':'#1e90ff','borderRadius':[3,3,0,0]}}]},height='175px',key='trend')
    with center:
        with st.container(border=True,key="panel_screen"):
            title('检测画面 · 最近事件证据')
            latest=next((r for r in rows if (store.root/r.get('evidence','')).is_file()),None)
            if latest:
                st.image(str(store.root/latest['evidence']),use_container_width=True)
                st.caption(f"历史事件证据 · {latest['site']} · {latest['created_at']}（非实时画面）")
            else:st.markdown('<div class="hud"><div>◎<strong>等待检测画面</strong>选择“视频监测”上传片段并开始分析<br>或选择“图片检测”查看疑似火焰位置</div></div>',unsafe_allow_html=True)
            st.caption('视频分析与图片检测请使用上方功能导航。')
        with st.container(border=True,key="panel_latest"):
            title('最新告警证据')
            if not rows:st.caption('暂无告警记录。')
            for r in rows[:3]:
                a,b=st.columns([1,3])
                evidence=store.root/r.get('evidence','')
                if evidence.is_file():a.image(str(evidence),use_container_width=True)
                b.markdown(f'<div class="log-row alarm"><time>{esc(r.get("created_at",""))}</time>{esc(r["site"])}<br><span class="badge {"wait" if r["status"]=="待接警" else "done" if r["status"]=="已结案" else ""}">{esc(r["status"])}</span></div>',unsafe_allow_html=True)
    with right:
        with st.container(border=True,key="panel_sites"):
            title('点位记录')
            st.caption('来源于已保存事件，不代表摄像头接入或在线状态。')
            for site in sites[:6]:st.markdown(f'<div class="site">▣ {esc(site)}<small>上传视频 · 在线状态未接入</small></div>',unsafe_allow_html=True)
            if not sites:st.caption('暂无已记录地点。')
        with st.container(border=True,key="panel_logs"):
            title('最近运行与处置日志')
            items=[]
            for when,cfg,result in runs[:8]:
                state={'completed':'完成','failed':'失败','incomplete':'不完整','running':'运行中或中断待核查'}.get(result.get('status'),'未知')
                items.append((when,f'视频分析：{state} · {cfg.get("site","")}'))
            for r in rows:
                for h in r.get('history',[]):items.append((local_time(h.get('at')),f'{h.get("operator","")} · {h.get("action","")} · {r["site"]}'))
            items.sort(key=lambda r:r[0] or datetime.min.replace(tzinfo=TZ),reverse=True)
            for when,message in items[:8]:st.markdown(f'<div class="log-row"><time>{esc(when.strftime("%m-%d %H:%M:%S") if when else "时间未知")}</time>{esc(message)}</div>',unsafe_allow_html=True)
            if not items:st.caption('暂无运行日志。')
            if skipped:st.caption(f'{skipped}条日志暂时无法读取。')
            st.caption('页面重运行时刷新；分析中进度见视频监测页。')
        with st.container(border=True,key="panel_model"):
            title('模型与默认参数')
            st.markdown('<div class="model-info">模型 <b>YOLO11s / fire</b><br>默认阈值 <b>0.1</b><br>默认采样 <b>1秒 / 帧</b><br>连续确认 <b>3次</b><br>阴性恢复 <b>5次</b><br>短信 <b>模拟发送</b></div>',unsafe_allow_html=True)
def event_table(rows):
    if not rows:return
    import pandas as pd
    data=[{'时间':(local_time(r.get('created_at')).strftime('%m-%d %H:%M:%S') if local_time(r.get('created_at')) else '未知'),'地点':r['site'],'置信度':round(r.get('score',0),4),'状态':r['status'],'证据':r.get('evidence',''),'操作':'展开下方记录接警／结案' if r['status']!='已结案' else '查看处置记录'} for r in rows]
    def status_color(value):
        colors={'待接警':'#ffae78','处理中':'#00d4ff','已结案':'#54e4a0'}
        return 'color: '+colors.get(value,'#e6f1ff')+'; font-weight: bold'
    styled=pd.DataFrame(data).style.map(status_color,subset=['状态']).format({'置信度':'{:.4f}'})
    st.dataframe(styled,use_container_width=True,hide_index=True)
