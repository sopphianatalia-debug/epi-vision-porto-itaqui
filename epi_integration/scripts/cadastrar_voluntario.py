"""Cadastro, teste e exclusão do rosto de um VOLUNTÁRIO (piloto de reconhecimento facial).

  cadastrar:  python scripts/cadastrar_voluntario.py
  testar:     python scripts/cadastrar_voluntario.py --testar
  apagar:     python scripts/cadastrar_voluntario.py --apagar

Regras: só voluntário, com consentimento escrito digitado. A foto NÃO é gravada: fica só na memória e vira um
vetor numérico criptografado no Identity. Nada de imagem em disco nem em log. Pode ser apagado a qualquer momento.
Requer o Identity rodando com EPI_FACE_PROVIDER=insightface (veja docs/TESTE_LOCAL.md).
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_seg = Path(__file__).resolve().parents[2] / ".local" / "segredos.env"
if not os.environ.get("EPI_JWT_SECRET") and _seg.exists():
    for line in _seg.read_text().splitlines():
        if line.startswith("EPI_JWT_SECRET="):
            os.environ["EPI_JWT_SECRET"] = line.split("=", 1)[1].strip()

TERMO = """
=== TERMO DE CONSENTIMENTO — PILOTO DE RECONHECIMENTO FACIAL (EPI Vision) ===
Finalidade: identificar você nos avisos de segurança do projeto acadêmico (teste/piloto).
O que é guardado: apenas um vetor numérico (template) criptografado. A FOTO NÃO É GUARDADA.
Quem acessa: somente o sistema e supervisores autorizados; todo acesso é registrado.
Participação voluntária: você pode recusar sem nenhuma consequência.
Seus direitos: você pode pedir a exclusão do template a qualquer momento (--apagar).
Este termo é de teste e ainda precisa de revisão jurídica/ética do grupo antes de uso real.
==============================================================================
"""


def _capturar(cam: int) -> str:
    import cv2  # noqa: PLC0415
    cap = cv2.VideoCapture(cam)
    if not cap.isOpened():
        sys.exit(f"Não consegui abrir a câmera {cam}.")
    print("Janela da câmera aberta. Olhe para a câmera, rosto bem iluminado e sem boné/máscara. "
          "ESPAÇO = capturar, Q = cancelar.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                sys.exit("Falha ao ler a câmera.")
            cv2.imshow("Cadastro de voluntario (ESPACO captura, Q cancela)", frame)
            k = cv2.waitKey(30) & 0xFF
            if k in (ord("q"), 27):
                sys.exit("Cancelado.")
            if k == 32:
                h, w = frame.shape[:2]
                if max(h, w) > 1280:
                    f = 1280 / max(h, w)
                    frame = cv2.resize(frame, (int(w * f), int(h * f)))
                ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                return base64.b64encode(buf.tobytes()).decode()      # só em memória
    finally:
        cap.release()
        cv2.destroyAllWindows()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--identity-url", default="http://127.0.0.1:8001/api/v1")
    ap.add_argument("--registration", default="DEMO-0001")
    ap.add_argument("--camera", type=int, default=0)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--testar", action="store_true", help="captura uma imagem e mostra se o sistema reconhece")
    g.add_argument("--apagar", action="store_true", help="apaga o template e revoga o consentimento")
    a = ap.parse_args()
    if not os.environ.get("EPI_JWT_SECRET"):
        print("Falta EPI_JWT_SECRET (rode antes ./scripts/subir_local.sh start).")
        return 2

    import httpx  # noqa: PLC0415
    from app.identity_client import IdentityClient  # noqa: PLC0415
    ident = IdentityClient(a.identity_url, timeout=60.0)     # o 1º uso do modelo pode demorar
    try:
        emp = next((e for e in ident.list_employees() if e["registration"] == a.registration), None)
        if not emp:
            print(f"Funcionário {a.registration} não existe. Rode antes scripts/criar_funcionario_demo.py.")
            return 2
        print(f"Funcionário: {emp['employee_code']} · {emp['name']}")

        if a.apagar:
            ident.delete_biometric(emp["id"])
            print("Template apagado e consentimento revogado.")
            return 0

        if a.testar:
            r = ident.match_image("CAM-TESTE", _capturar(a.camera))
            print(f"Resultado: {r.get('status')} · funcionário={r.get('employee_id')} · "
                  f"similaridade={r.get('similarity_score')} · confiança={r.get('confidence')}")
            if r.get("status") == "MATCHED" and r.get("employee_id") == emp["employee_code"]:
                print("Reconheceu corretamente.")
            return 0

        print(TERMO)
        if input('Para participar, digite exatamente  ACEITO  (qualquer outra coisa cancela): ').strip() != "ACEITO":
            print("Sem consentimento: nada foi feito.")
            return 1
        r = ident.enroll_image(emp["id"], _capturar(a.camera), consent=True)
        print(f"Cadastrado. Status biométrico: {r.get('biometric_status', r)}")
        print("Agora teste:  python scripts/cadastrar_voluntario.py --testar")
        return 0
    except httpx.HTTPStatusError as exc:
        print(f"Erro {exc.response.status_code}: {exc.response.text[:300]}")
        return 1
    except httpx.HTTPError as exc:
        print(f"Identity inacessível ({exc.__class__.__name__}). Está no ar na porta 8001?")
        return 1
    finally:
        ident.close()


if __name__ == "__main__":
    raise SystemExit(main())
