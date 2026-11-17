from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from app.api.deps import get_service
from app.api.schemas import (
    BatchRequest,
    BatchResponse,
    EvaluateResponse,
    FrameIn,
)
from app.compliance import PPEComplianceService
from app.config import get_settings
from app.dashboard import build_dashboard

router = APIRouter()


@router.get("/health", tags=["health"])
def health():
    return {"status": "ok", "pose": get_settings().pose_provider}


@router.get("/config", tags=["config"])
def config():
    s = get_settings()
    return {
        "required_ppe": s.required_ppe,
        "temporal_window": s.temporal_window,
        "confidence_threshold": s.confidence_threshold,
        "pose_provider": s.pose_provider,
    }


@router.post("/compliance/evaluate", response_model=EvaluateResponse, tags=["compliance"])
def evaluate(body: FrameIn, service: PPEComplianceService = Depends(get_service)):
    result, evidence = service.evaluate(body.to_observation())
    return EvaluateResponse(
        result=result.to_dict(),
        dashboard=build_dashboard(result),
        evidence=evidence,
    )


@router.post("/compliance/evaluate-batch", response_model=BatchResponse, tags=["compliance"])
def evaluate_batch(body: BatchRequest, service: PPEComplianceService = Depends(get_service)):
    """
    Processa uma sequência de frames (demonstra a análise temporal em uma só
    chamada). Retorna o resultado final consolidado do último frame.
    """
    last_result = None
    all_evidence: list[dict] = []
    for frame in body.frames:
        last_result, ev = service.evaluate(frame.to_observation())
        all_evidence.extend(ev)
    if last_result is None:
        return BatchResponse(final={}, dashboard={}, frames_processed=0, evidence=[])
    return BatchResponse(
        final=last_result.to_dict(),
        dashboard=build_dashboard(last_result),
        frames_processed=len(body.frames),
        evidence=all_evidence,
    )


@router.get("/compliance/state", tags=["compliance"])
def state(service: PPEComplianceService = Depends(get_service)):
    return service.latest_states()


@router.get("/compliance/evidence", tags=["evidence"])
def evidence(limit: int = 50, service: PPEComplianceService = Depends(get_service)):
    return service.evidence.recent(limit)


_DASHBOARD_HTML = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>EPI — Conformidade</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body{font-family:system-ui,Arial,sans-serif;background:#0f1115;color:#e8e8e8;margin:0;padding:24px}
 h1{font-size:20px;font-weight:600}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-top:16px}
 .card{background:#1a1d24;border:1px solid #2a2e38;border-radius:12px;padding:16px}
 .name{font-weight:600;margin-bottom:8px}
 .item{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #23262f}
 .overall{margin-top:10px;font-weight:700}
 .muted{color:#8a90a0;font-size:12px}
 button{background:#2a2e38;color:#e8e8e8;border:0;border-radius:8px;padding:8px 12px;cursor:pointer}
</style></head><body>
 <h1>EPI Vision — Dashboard de Conformidade</h1>
 <p class="muted">Atualiza a cada 2s a partir de <code>/api/v1/compliance/state</code>.
   <button onclick="load()">Atualizar agora</button></p>
 <div id="grid" class="grid"></div>
<script>
const VIEW={PROPER:['🟢','Correto'],PRESENT:['🟢','Presente'],MISSING:['🔴','Ausente'],
 IMPROPER:['🔴','Incorreto'],NOT_VISIBLE:['⚪','Não verificável'],UNKNOWN:['🟡','Indeterminado']};
const OVR={COMPLIANT:['✅','CONFORME'],PARTIAL_NON_COMPLIANCE:['⚠️','PARCIALMENTE NÃO CONFORME'],
 NON_COMPLIANT:['⚠️','NÃO CONFORME'],UNDETERMINED:['❓','NÃO DETERMINADO']};
function row(label,st){const[e,t]=VIEW[st]||['❔',st];
 return `<div class="item"><span>${label}</span><span>${e} ${t}</span></div>`;}
async function load(){
 const r=await fetch('/api/v1/compliance/state'); const data=await r.json();
 const g=document.getElementById('grid');
 if(!data.length){g.innerHTML='<p class="muted">Nenhuma pessoa avaliada ainda. Envie frames em /docs.</p>';return;}
 g.innerHTML=data.map(p=>{
  const[oe,ot]=OVR[p.overall]||['❔',p.overall];
  const gl=p.gloves; const gtxt = gl.summary==='not_verifiable'?'⚪ Não verificável':(gl.left===gl.right?VIEW[gl.left][0]+' '+VIEW[gl.left][1]:'🔴 '+gl.summary);
  return `<div class="card">
   <div class="name">${p.employee_id||p.person_track_id}</div>
   ${row('Capacete',p.helmet.status)}
   ${row('Colete',p.vest.status)}
   <div class="item"><span>Luvas</span><span>${gtxt}</span></div>
   ${row('Óculos',p.glasses.status)}
   ${row('Botas',p.boots.status)}
   <div class="overall">${oe} ${ot}</div>
  </div>`;}).join('');
}
load(); setInterval(load,2000);
</script></body></html>"""


@router.get("/dashboard", response_class=HTMLResponse, tags=["dashboard"])
def dashboard_page():
    return HTMLResponse(_DASHBOARD_HTML)
