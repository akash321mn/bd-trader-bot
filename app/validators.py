from .data.pairs import (
    USER_TO_DERIV, NORMALIZE, TF_TO_GRAN,
    normalize_symbol as _norm_sym,
    to_deriv_symbol as _to_deriv,
)

def is_valid_pair(sym: str) -> bool:
    s = _norm_sym(sym)
    return s in USER_TO_DERIV

def is_otc_pair(sym: str) -> bool:
    return "OTC" in str(sym or "").upper()

def normalize_symbol(sym: str) -> str:
    return _norm_sym(sym)

def to_deriv_symbol(sym: str) -> str | None:
    return _to_deriv(sym)

def is_supported_tf(tf) -> bool:
    tf_str = str(tf).strip().upper()
    return tf_str in TF_TO_GRAN

def granularity(tf) -> int:
    tf_str = str(tf).strip().upper()
    return TF_TO_GRAN[tf_str]

def supported_user_symbols() -> list[str]:
    return list(USER_TO_DERIV.keys())
