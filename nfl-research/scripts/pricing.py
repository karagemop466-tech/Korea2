"""Small mathematical primitives; not a model, data feed or betting system."""
import math


def _prob(p):
    if not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError('probability must be finite and in [0, 1]')


def fair_decimal_no_push(p):
    _prob(p)
    if p == 0:
        raise ValueError('zero probability has no finite fair price')
    return 1 / p


def expected_return(decimal_odds, p_win, p_loss):
    """Unit-stake net return, with all remaining probability refunded on push/void."""
    _prob(p_win); _prob(p_loss)
    if p_win + p_loss > 1 + 1e-12:
        raise ValueError('win and loss probabilities exceed one')
    if not math.isfinite(decimal_odds) or decimal_odds <= 1:
        raise ValueError('decimal odds must exceed one')
    return p_win * (decimal_odds - 1) - p_loss


def binary_dependence(p_a, p_b, p_joint):
    """Return phi for a coherent two-event distribution; constant marginals undefined."""
    for p in (p_a, p_b, p_joint): _prob(p)
    if p_joint < max(0, p_a + p_b - 1) - 1e-12 or p_joint > min(p_a, p_b) + 1e-12:
        raise ValueError('joint probability violates probability bounds')
    denom = math.sqrt(p_a * (1 - p_a) * p_b * (1 - p_b))
    if denom == 0:
        raise ValueError('constant marginal: correlation undefined')
    return (p_joint - p_a * p_b) / denom
