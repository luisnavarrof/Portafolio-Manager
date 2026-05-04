"""Persistencia del Excel de transacciones.

Escribe local + opcionalmente commitea a GitHub vía la Contents API,
para que la edición desde la app desplegada en Streamlit Cloud persista.

Para activar la sincronización con GitHub, agregar a `.streamlit/secrets.toml`
(o al panel de Secrets en Streamlit Cloud):

    [github]
    token = "ghp_xxxxx"             # PAT con permiso 'Contents: read+write'
    repo = "luisnavarrof/Portafolio-Manager"
    branch = "main"
    file_path = "data/transactions.xlsx"
"""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import base64
import pandas as pd
import requests

from .loader import TX_PATH

EXCEL_COLS = ["Fecha", "Tipo", "Activo", "Monto (USD)", "Etiqueta"]


def df_to_excel_bytes(tx: pd.DataFrame) -> bytes:
    """Serializa el DataFrame al formato del Excel original (5 columnas)."""
    out = tx.copy()
    rename_back = {
        "fecha": "Fecha", "tipo": "Tipo", "activo": "Activo",
        "monto_usd": "Monto (USD)", "etiqueta": "Etiqueta",
    }
    out = out.rename(columns=rename_back)
    if "is_close" in out.columns:
        out = out.drop(columns=["is_close"])
    out = out[EXCEL_COLS]
    out["Fecha"] = pd.to_datetime(out["Fecha"]).dt.strftime("%Y-%m-%d")
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        out.to_excel(w, index=False, sheet_name="Transacciones")
    return buf.getvalue()


def save_local(tx: pd.DataFrame, path: Path | str = TX_PATH) -> None:
    Path(path).write_bytes(df_to_excel_bytes(tx))


def github_commit(content: bytes, *, token: str, repo: str, branch: str,
                  file_path: str, message: str) -> dict:
    """Crea/actualiza un archivo binario via la Contents API."""
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    sha = None
    r = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
    if r.status_code == 200:
        sha = r.json().get("sha")
    payload = {
        "message": message,
        "content": base64.b64encode(content).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=headers, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def save_transactions(tx: pd.DataFrame, *, gh_secrets: dict | None = None,
                      message: str = "Update transactions") -> tuple[bool, str]:
    """Guarda el Excel localmente y, si hay secrets de GitHub, también commitea.

    Devuelve (ok, mensaje_humano).
    """
    blob = df_to_excel_bytes(tx)
    Path(TX_PATH).write_bytes(blob)
    if not gh_secrets:
        return True, "Guardado localmente (sin sync a GitHub)."
    try:
        github_commit(
            blob,
            token=gh_secrets["token"],
            repo=gh_secrets["repo"],
            branch=gh_secrets.get("branch", "main"),
            file_path=gh_secrets.get("file_path", "data/transactions.xlsx"),
            message=message,
        )
        return True, "Guardado y sincronizado a GitHub. La app se redesplegará en ~30s."
    except requests.HTTPError as ex:
        return False, f"Guardado local OK, pero falló commit a GitHub: {ex.response.status_code} {ex.response.text[:200]}"
    except Exception as ex:
        return False, f"Guardado local OK, pero falló commit a GitHub: {ex}"
