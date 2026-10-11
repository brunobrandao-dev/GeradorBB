# auth.py — Autenticação via Supabase
#
# Usa supabase-py v2. Instale com: pip install supabase
# Sessão persistida em session.json (tokens de acesso/refresh).

import json
import datetime
from pathlib import Path

SUPABASE_URL = "https://agsubkvhwyeiwtiallsf.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFnc3Via3Zod3llaXd0aWFsbHNmIiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3OTEzMTUwMzUsImV4cCI6MjEwNjg5MTAzNX0"
    ".lI0aEwToOAaKJgey0h2xs505mmk8T6AwFlXPWA7mh8k"
)

SESSION_FILE = Path(__file__).parent / "session.json"

_client = None


def _sb():
    """Retorna (e inicializa, se necessário) o cliente Supabase."""
    global _client
    if _client is None:
        try:
            from supabase import create_client
            _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        except ImportError as e:
            import traceback
            Path(__file__).parent.joinpath("erro_supabase.txt").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
            raise RuntimeError(
                f"Pacote 'supabase' não encontrado.\n"
                f"Execute: pip install supabase\n\nDetalhe: {e}"
            )
        except Exception as e:
            import traceback
            Path(__file__).parent.joinpath("erro_supabase.txt").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
            raise
    return _client


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _salvar_sessao(dados: dict):
    SESSION_FILE.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _limpar_sessao():
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


def _nome_do_user(user) -> str:
    meta = user.user_metadata or {}
    return meta.get("nome") or (user.email or "").split("@")[0].capitalize()


def _enrich_user(dados: dict) -> dict:
    """Busca is_admin do perfil e adiciona ao dict do usuário."""
    try:
        resp = (
            _sb()
            .table("profiles")
            .select("is_admin")
            .eq("id", dados["user_id"])
            .limit(1)
            .execute()
        )
        if resp.data:
            dados["is_admin"] = bool(resp.data[0].get("is_admin", False))
        else:
            dados["is_admin"] = False
    except Exception:
        dados["is_admin"] = False
    return dados


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def login(email: str, senha: str) -> dict:
    """
    Retorna:
        {"ok": True,  "user": {"user_id", "nome", "email", "access_token", "refresh_token"}}
        {"ok": False, "erro": "mensagem"}
    """
    email = email.strip().lower()
    if not email or not senha:
        return {"ok": False, "erro": "Preencha e-mail e senha."}

    try:
        resp = _sb().auth.sign_in_with_password({"email": email, "password": senha})
        user    = resp.user
        session = resp.session
        dados = {
            "user_id":       str(user.id),
            "nome":          _nome_do_user(user),
            "email":         user.email,
            "access_token":  session.access_token,
            "refresh_token": session.refresh_token,
        }
        _salvar_sessao(dados)
        _enrich_user(dados)
        return {"ok": True, "user": dados}

    except Exception as e:
        msg = str(e)
        if "Invalid login credentials" in msg:
            return {"ok": False, "erro": "E-mail ou senha incorretos."}
        if "Email not confirmed" in msg:
            return {"ok": False, "erro": "Confirme seu e-mail antes de entrar."}
        if "network" in msg.lower() or "connection" in msg.lower():
            return {"ok": False, "erro": "Sem conexão com a internet."}
        return {"ok": False, "erro": f"Erro ao entrar: {msg}"}


def cadastrar(email: str, senha: str, nome: str) -> dict:
    """
    Retorna:
        {"ok": True,  "user": {...}}                           — logou direto
        {"ok": True,  "confirmar_email": True, "user": {...}} — precisa confirmar e-mail
        {"ok": False, "erro": "mensagem"}
    """
    email = email.strip().lower()
    nome  = nome.strip()

    if not email or not senha or not nome:
        return {"ok": False, "erro": "Preencha todos os campos."}
    if len(senha) < 6:
        return {"ok": False, "erro": "A senha deve ter ao menos 6 caracteres."}

    try:
        resp = _sb().auth.sign_up({
            "email":    email,
            "password": senha,
            "options":  {"data": {"nome": nome}},
        })

        if resp.user is None:
            return {"ok": False, "erro": "Erro ao criar conta."}

        user = resp.user

        # Se "Confirm email" estiver DESATIVADO no Supabase, a sessão já vem aqui
        if resp.session:
            dados = {
                "user_id":       str(user.id),
                "nome":          nome,
                "email":         email,
                "access_token":  resp.session.access_token,
                "refresh_token": resp.session.refresh_token,
            }
            _salvar_sessao(dados)
            return {"ok": True, "user": dados}

        # "Confirm email" ATIVADO — pede ao usuário para verificar a caixa de entrada
        return {
            "ok":             True,
            "confirmar_email": True,
            "user":           {"user_id": None, "nome": nome, "email": email},
        }

    except Exception as e:
        import traceback
        Path(__file__).parent.joinpath("erro_cadastro.txt").write_text(
            traceback.format_exc(), encoding="utf-8"
        )
        msg = str(e)
        if any(x in msg for x in ("already registered", "already exists", "User already registered")):
            return {"ok": False, "erro": "Este e-mail já está cadastrado."}
        if "network" in msg.lower() or "connection" in msg.lower():
            return {"ok": False, "erro": "Sem conexão com a internet."}
        return {"ok": False, "erro": f"Erro ao cadastrar: {msg}"}


def recuperar_senha(email: str) -> dict:
    """
    Retorna:
        {"ok": True,  "msg": "..."}
        {"ok": False, "erro": "mensagem"}
    """
    email = email.strip().lower()
    if not email:
        return {"ok": False, "erro": "Informe o e-mail."}
    try:
        _sb().auth.reset_password_for_email(email)
    except Exception:
        pass  # Sempre retorna sucesso para não vazar se o e-mail existe ou não
    return {
        "ok":  True,
        "msg": f"Se '{email}' estiver cadastrado, você receberá o link em breve.",
    }


def verificar_licenca(user_id: str, access_token: str | None = None) -> dict:
    """
    Retorna:
        {"valida": True,  "tipo": "7dias"|"15dias"|"30dias"|"60dias"|"90dias"|"vitalicio",
         "expira": "YYYY-MM-DD"|None, "dias_restantes": int|None}
        {"valida": False, "tipo": None, "expira": None, "dias_restantes": None}
    """
    _sem_licenca = {"valida": False, "tipo": None, "expira": None, "dias_restantes": None}

    if not user_id:
        return _sem_licenca

    try:
        resp = (
            _sb()
            .table("licencas")
            .select("*")
            .eq("user_id", user_id)
            .eq("ativa", True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not resp.data:
            return _sem_licenca

        lic = resp.data[0]

        if lic["tipo"] == "vitalicio":
            return {"valida": True, "tipo": "vitalicio", "expira": None, "dias_restantes": None}

        expira = datetime.date.fromisoformat(lic["expira"])
        hoje   = datetime.date.today()
        delta  = (expira - hoje).days
        return {
            "valida":          delta >= 0,
            "tipo":            lic["tipo"],
            "expira":          lic["expira"],
            "dias_restantes":  max(delta, 0),
        }

    except Exception:
        return _sem_licenca


def logout():
    """Encerra a sessão local e no Supabase."""
    try:
        _sb().auth.sign_out()
    except Exception:
        pass
    _limpar_sessao()


def admin_listar_usuarios() -> list[dict]:
    """
    Admin only: retorna todos os usuários com status de licença.
    Requer que o admin esteja logado (RLS usa auth.uid()).
    """
    import datetime as _dt
    try:
        resp_p = (
            _sb()
            .table("profiles")
            .select("id, nome, email, is_admin, created_at")
            .order("created_at", desc=True)
            .execute()
        )
        perfis = resp_p.data or []

        resp_l = (
            _sb()
            .table("licencas")
            .select("user_id, tipo, expira, ativa, created_at")
            .eq("ativa", True)
            .execute()
        )
        # último registro por user (já ordenado por created_at desc não garantido,
        # pega o primeiro encontrado)
        lic_map: dict = {}
        for l in (resp_l.data or []):
            uid = l["user_id"]
            if uid not in lic_map:
                lic_map[uid] = l

        resultado = []
        for p in perfis:
            uid = p["id"]
            lic = lic_map.get(uid)
            if lic:
                if lic["tipo"] == "vitalicio":
                    lic_status, lic_dias = "vitalicio", None
                else:
                    try:
                        expira = _dt.date.fromisoformat(lic["expira"])
                        delta  = (expira - _dt.date.today()).days
                        lic_status = lic["tipo"]
                        lic_dias   = max(delta, 0) if delta >= 0 else -1
                    except Exception:
                        lic_status, lic_dias = lic["tipo"], None
            else:
                lic_status, lic_dias = None, None

            resultado.append({
                "user_id":   uid,
                "nome":      p.get("nome", ""),
                "email":     p.get("email", ""),
                "is_admin":  p.get("is_admin", False),
                "criado_em": (p.get("created_at") or "")[:10],
                "lic_tipo":  lic_status,
                "lic_dias":  lic_dias,
            })
        return resultado
    except Exception:
        return []


def admin_criar_licenca(user_id: str, tipo: str) -> dict:
    """
    Admin only: cria (substitui) licença para um usuário.
    tipo: 'trial' | 'mensal' | 'trimestral' | 'semestral' | 'vitalicio'
    """
    import datetime as _dt
    _dias_map = {"trial": 3, "mensal": 30, "trimestral": 90, "semestral": 180}
    try:
        # Desativa anteriores
        _sb().table("licencas").update({"ativa": False}).eq("user_id", user_id).execute()
        # Calcula expiração
        if tipo == "vitalicio":
            expira = None
        else:
            dias   = _dias_map.get(tipo, 30)
            expira = (_dt.date.today() + _dt.timedelta(days=dias)).isoformat()
        # Insere nova
        _sb().table("licencas").insert({
            "user_id": user_id,
            "tipo":    tipo,
            "expira":  expira,
            "ativa":   True,
        }).execute()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erro": str(e)}


def admin_revogar_licenca(user_id: str) -> dict:
    """Admin only: desativa todas as licenças do usuário."""
    try:
        _sb().table("licencas").update({"ativa": False}).eq("user_id", user_id).execute()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "erro": str(e)}


def carregar_sessao() -> dict | None:
    """
    Tenta restaurar a sessão salva em disco.
    Renova o token automaticamente se necessário.
    Retorna o dict de sessão ou None se não houver sessão válida.
    """
    if not SESSION_FILE.exists():
        return None

    try:
        dados = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        access  = dados.get("access_token")
        refresh = dados.get("refresh_token")
        if not access or not refresh:
            return None

        resp = _sb().auth.set_session(access, refresh)

        if resp.user and resp.session:
            dados["user_id"]       = str(resp.user.id)
            dados["email"]         = resp.user.email
            dados["nome"]          = _nome_do_user(resp.user)
            dados["access_token"]  = resp.session.access_token
            dados["refresh_token"] = resp.session.refresh_token
            _salvar_sessao(dados)
            _enrich_user(dados)
            return dados

    except Exception:
        pass

    _limpar_sessao()
    return None
