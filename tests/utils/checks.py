def check_vault_empty(vault):
    assert vault.totalAssets() == 0
    assert vault.totalSupply() == 0
    assert vault.totalIdle() == 0
    assert vault.totalDebt() == 0


def check_revoked_strategy(strategyParams):
    assert strategyParams.activation == 0
    assert strategyParams.lastReport == 0
    assert strategyParams.currentDebt == 0
    assert strategyParams.maxDebt == 0
