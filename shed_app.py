"""Electric bicycle shed video demonstration with simulated SMS."""
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from datetime import datetime

import streamlit as st
from shed_events import Store, Gate
from shed_runlog import RunLog, digest

ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='棚安火情监测系统',page_icon='🚲',layout='wide')
from shed_ui import header, dashboard, event_table
with (ROOT/'assets/style.css').open(encoding='utf-8') as css:
    st.markdown('<style>'+css.read()+'</style>',unsafe_allow_html=True)
header()
operator_name='匿名演示用户'
st.caption('开放演示 · 所有人均可检测、接警和结案；处置记录标记为匿名演示用户。')
store=Store(Path(os.environ.get('SHED_DATA_DIR',str(ROOT/'shed_runtime'))))
overview=store.all()
@st.cache_resource
def model_resource(path, revision):
    import threading
    from ultralytics import YOLO
    import torch
    torch.set_num_threads(4)
    return YOLO(path), threading.Lock()

def find_weight():
    candidates=[ROOT/'artifacts/best.pt',ROOT/'best.pt',ROOT.parent/'best.pt']
    return next((p for p in candidates if p.is_file()),candidates[0])

def predict(frame,threshold):
    p=find_weight()
    if not p.exists():
        raise ValueError('请将模型放在 artifacts/best.pt')
    model,lock=model_resource(str(p),p.stat().st_mtime_ns)
    classes=[k for k,v in model.names.items() if v.lower()=='fire']
    if not classes:
        raise ValueError('模型中没有 fire 类别')
    with lock:
        r=model.predict(frame,conf=threshold,classes=classes,imgsz=960,device='cpu',verbose=False)[0]
        score=float(r.boxes.conf.max()) if len(r.boxes) else 0.0
        return score, r.plot(), [dict(xyxy=b.xyxy[0].tolist(),confidence=float(b.conf[0]),class_id=int(b.cls[0])) for b in r.boxes]

home,image_tab,video_tab,desk=st.tabs(['主控制台','图片检测','视频监测','接警处置'])
with home:
    dashboard(store,overview)
    st.subheader('事件记录总览')
    event_table(overview)
with video_tab:
    st.markdown('<div class="section-kicker">VIDEO MONITORING</div>',unsafe_allow_html=True)
    st.subheader('从一段车棚视频开始')
    st.caption('检测按采样帧运行，不是实时摄像头；连续命中用于演示确认，未通过车棚场景校准。')
    controls,screen=st.columns([1,2.3],gap='large')
    with controls:
        site=st.text_input('车棚位置','浙江万里学院 · 示例车棚')
        contact=st.text_input('演示值班人员','保卫部测试值班员')
        with st.expander('检测参数 · 默认使用现有模型配置',expanded=False):
            threshold=st.number_input('检测阈值',0.001,0.9999,0.1,format='%.4f')
            interval=st.selectbox('采样间隔（视频秒）',[0.5,1.0,2.0],index=1)
            required=st.number_input('连续命中采样帧数',1,10,3)
            st.caption('连续 5 个采样帧未检出后，才允许为新的火情生成事件。同一地点、视频和配置重复运行会记录新实验，但复用已确认事件。')
        st.markdown('<div class="flow"><span>01 上传视频</span><span>02 识别异常</span><span>03 生成模拟短信</span><span>04 人员接警处置</span></div>',unsafe_allow_html=True)
        upload=st.file_uploader('上传视频（建议短视频，最多分析前 10 分钟）',type=['mp4','avi','mov','mkv'])
        start_analysis=st.button('开始视频分析',disabled=upload is None,type='primary',use_container_width=True)
    with screen:
        if upload:
            st.video(upload)
        else:
            st.markdown('<div class="empty">▷<strong>监测画面待接入</strong>上传一段车棚视频，查看疑似火情与事件记录<br><small>建议使用短视频 · 最多分析前 10 分钟</small></div>',unsafe_allow_html=True)
        if start_analysis:
            if not site.strip() or not contact.strip():
                st.error('请填写车棚位置与值班人员')
            else:
                cap=None; temp=None; runlog=None
                try:
                    import cv2
                    blob=upload.getvalue()
                    video_hash=hashlib.sha256(blob).hexdigest()
                    model_hash=digest(find_weight())
                    configuration=dict(site=site,video=upload.name,video_sha256=video_hash,model_sha256=model_hash,
                        threshold=threshold,interval=float(interval),required=int(required),clear=5,imgsz=960,device='cpu',
                        max_video_seconds=600,sms_mode='模拟发送',
                        code_sha256={n:digest(ROOT/n) for n in ['shed_app.py','shed_events.py','shed_runlog.py','shed_auth.py']})
                    identity={k:configuration[k] for k in ['site','video_sha256','model_sha256','threshold','interval','required','clear','imgsz','device']}
                    batch_key=hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                    runlog=RunLog(store.root,configuration)
                    with tempfile.NamedTemporaryFile(suffix=Path(upload.name).suffix,delete=False) as f:
                        f.write(blob);temp=f.name
                    cap=cv2.VideoCapture(temp)
                    fps=cap.get(cv2.CAP_PROP_FPS)
                    expected_frames=cap.get(cv2.CAP_PROP_FRAME_COUNT)
                    if not cap.isOpened() or not 0<fps<1000:
                        raise ValueError('无法解码视频或帧率无效，请转换为标准 MP4 后重试')
                    gate=Gate(int(required));stride=max(1,round(fps*interval))
                    preview=st.empty();status=st.empty();start=time.perf_counter()
                    samples=0;events=[];idx=0;inference=0.;ended=False
                    while idx/fps<600:
                        ok,frame=cap.read()
                        if not ok:
                            ended=True;break
                        t=idx/fps;idx+=1
                        if (idx-1)%stride:continue
                        tick=time.perf_counter();score,marked,boxes=predict(frame,threshold)
                        inference+=time.perf_counter()-tick;samples+=1
                        first=gate.step(score>=threshold,t)
                        runlog.frame(dict(frame_index=idx-1,video_seconds=t,time_basis='frame_index/fps',
                            score=score,boxes=boxes,positive=score>=threshold,confirmation_start=first,
                            inference_seconds=time.perf_counter()-tick))
                        preview.image(marked,channels='BGR',caption=f'视频 {t:.1f}s · '+('疑似火情' if score>=threshold else '本采样帧未检出'),use_container_width=True)
                        if first is not None:
                            # Store evidence before publishing an actionable event.
                            import uuid
                            event_key=batch_key+':'+str(first)
                            evidence=hashlib.sha256(event_key.encode()).hexdigest()+'.jpg'
                            if not (store.root/evidence).exists() and not cv2.imwrite(str(store.root/evidence),marked):
                                raise ValueError('告警截图保存失败')
                            eid=store.create(event_key=event_key,run_id=runlog.path.name,site=site,contact=contact,video=upload.name,video_sha256=hashlib.sha256(blob).hexdigest(),
                                video_time=t,first_positive_time=first,confirmation_video_seconds=t-first,
                                analysis_elapsed_seconds=time.perf_counter()-start,threshold=threshold,score=score,evidence=evidence)
                            events.append(eid)
                        status.info(f'已分析 {samples} 个采样帧，关联 {len(events)} 个事件（含复用）· 短信仅模拟')
                    if samples==0:raise ValueError('视频未解码出任何有效帧')
                    result=dict(video=upload.name,samples=samples,event_ids=events,elapsed_seconds=round(time.perf_counter()-start,2),
                        mean_inference_seconds=round(inference/samples,3),coverage='解码器返回视频结束（损坏文件也可能提前结束）' if ended else '仅分析前10分钟',sms_mode='模拟发送')
                    result.update(status='completed',run_id=runlog.path.name,decoded_frames=idx,expected_frames=expected_frames,
                        possible_truncation=bool(ended and expected_frames>0 and idx<expected_frames-1))
                    if result['possible_truncation']:
                        result['status']='incomplete'; st.warning('解码提前结束，记录不完整，不能作为全视频验证结果。')
                    runlog.save('result.json',result)
                    st.session_state['last_analysis']=result
                    if result['status']=='completed': st.success('本轮分析完成，请进入“接警与处置”处理事件。')
                except Exception as e:
                    if runlog is not None: runlog.save('result.json',dict(status='failed',error=repr(e)))
                    st.error(f'视频分析失败：{e}。此前已生成的事件仍保留在接警台。')
                finally:
                    if cap is not None:cap.release()
                    if temp:Path(temp).unlink(missing_ok=True)
        if 'last_analysis' in st.session_state:
            result=st.session_state['last_analysis']
            st.subheader('本轮分析概览')
            cols=st.columns(3)
            cols[0].metric('采样帧数',result['samples'])
            cols[1].metric('关联事件',len(result['event_ids']))
            cols[2].metric('分析用时',f"{result['elapsed_seconds']:.1f} 秒")
            st.caption(result['coverage'])
            with st.expander('查看完整分析记录'):st.json(result)

with desk:
    st.markdown('<div class="section-kicker">INCIDENT RESPONSE</div>',unsafe_allow_html=True)
    st.subheader('保卫部接警台')
    st.caption('开放演示接警台：任何访客均可接警与结案，操作统一标记为匿名演示用户。短信仅模拟发送。')
    if st.button('刷新事件'):st.rerun()
    rows=store.all()
    a,b,c=st.columns(3)
    a.metric('待接警',sum(r['status']=='待接警' for r in rows))
    b.metric('处理中',sum(r['status']=='处理中' for r in rows))
    c.metric('已结案',sum(r['status']=='已结案' for r in rows))
    st.caption('人工判为误报的事件数：'+str(sum(r.get('verdict')=='误报' for r in rows))+'。缺少完整真实标注，暂不计算误报率或漏检率。')
    st.download_button('导出事件与处置记录',json.dumps(rows,ensure_ascii=False,indent=2),'shed_events.json','application/json')
    if st.button('生成事件及证据备份（请在分析完成后操作）'):
        st.session_state['backup_bytes']=store.export_backup()
    if 'backup_bytes' in st.session_state:
        st.download_button('下载备份ZIP',st.session_state['backup_bytes'],'shed_backup.zip','application/zip')
    filter_status=st.selectbox('查看事件',['全部','待接警','处理中','已结案'])
    rows=[r for r in rows if filter_status=='全部' or r['status']==filter_status]
    event_table(rows)
    if not rows:st.info('当前没有符合条件的事件。视频分析生成的告警会出现在这里。')
    for r in rows:
        badge={'待接警':'🔴','处理中':'🟠','已结案':'🟢'}[r['status']]
        with st.expander(f"{badge} {r['status']} ｜ {r['site']} ｜ {r['id'][:8]}",expanded=False):
            st.write(f"值班人员：{r['contact']} ｜ 视频：{r['video']} ｜ 视频时间：{r['video_time']:.1f}s")
            st.write(f"连续确认耗时（视频时间）：{r['confirmation_video_seconds']:.1f}s；从分析开始至告警（实际耗时）：{r['analysis_elapsed_seconds']:.2f}s")
            if r.get('ack_at'):
                st.write(f"告警到接警：{(datetime.fromisoformat(r['ack_at'])-datetime.fromisoformat(r['created_at'])).total_seconds():.1f}s")
            evidence=store.root/r['evidence']
            if evidence.exists():st.image(str(evidence),use_container_width=True)
            st.markdown('**模拟短信预览**')
            st.info(r['sms']['body']);st.caption(r['sms']['status']+'；不提供真实送达时间。')
            if r['status']!='已结案':
                with st.form(r['id']):
                    operator=operator_name
                    st.caption('处置账号：'+operator)
                    verdict=st.selectbox('核查结论',['确认火情','误报','无法确认']) if r['status']=='处理中' else ''
                    note=st.text_area('处置说明（结案必填）')
                    action='接警' if r['status']=='待接警' else '结案'
                    if st.form_submit_button('确认'+action):
                        try:store.transition(r['id'],action,operator,note,verdict);st.rerun()
                        except ValueError as e:st.error(str(e))
            st.markdown('**处置时间线**')
            if not r['history']:st.caption('等待值班人员接警。')
            for entry in r['history']:
                st.text(f"{entry['at']}  ·  {entry['operator']}  ·  {entry['action']}")
                if entry['note']:st.text(entry['note'])

with image_tab:
    st.markdown('<div class="section-kicker">IMAGE INSPECTION</div>',unsafe_allow_html=True)
    st.subheader('现场图片快速检查')
    st.caption('上传车棚现场照片，查看模型标注的疑似火情位置。')
    picture=st.file_uploader('上传车棚图片',type=['jpg','jpeg','png'],key='picture')
    if st.button('检测图片',disabled=picture is None):
        try:
            import numpy as np
            from PIL import Image,ImageOps
            im=ImageOps.exif_transpose(Image.open(picture)).convert('RGB')
            if im.width*im.height>20000000:raise ValueError('图片超过2000万像素')
            score,marked,boxes=predict(np.asarray(im)[:,:,::-1].copy(),threshold)
            st.image(marked,channels='BGR',use_container_width=True)
            st.write('发现疑似火情' if score>=threshold else '本次未检出达到阈值的火情')
            st.caption('图片检测仅作辅助展示，不自动生成视频告警事件。')
        except Exception as e:st.error(str(e))
st.caption('现有模型为原型基础，未检出不代表现场安全；纯烟雾能力及车棚场景效果尚需验证。')

