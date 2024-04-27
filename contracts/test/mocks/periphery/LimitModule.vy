# @version 0.3.7

interface IVault:
    def totalAssets() -> uint256: view

enforceWhitelist: public(bool)

whitelist: public(HashMap[address, bool])

defaultDepositLimit: public(uint256)

defaultWithdrawLimit: public(uint256)

@external
def __init__(
    defaultDepositLimit: uint256,
    defaultWithdrawLimit: uint256,
    enforceWhitelist: bool
):
    self.defaultDepositLimit = defaultDepositLimit
    self.defaultWithdrawLimit = defaultWithdrawLimit
    self.enforceWhitelist = enforceWhitelist

@view
@external
def availableDepositLimit(receiver: address) -> uint256:
    if self.enforceWhitelist:
        if not self.whitelist[receiver]:
            return 0

    if self.defaultDepositLimit == MAX_UINT256:
        return MAX_UINT256
        
    return self.defaultDepositLimit - IVault(msg.sender).totalAssets()

@view
@external
def availableWithdrawLimit(owner: address, maxLoss: uint256, strategies: DynArray[address, 10]) -> uint256:
    return self.defaultWithdrawLimit

@external
def setWhitelist(list: address):
    self.whitelist[list] = True

@external
def setDefaultDepositLimit(limit: uint256):
    self.defaultDepositLimit = limit

@external
def setDefaultWithdrawLimit(limit: uint256):
    self.defaultWithdrawLimit = limit

@external
def setEnforceWhitelist(enforce: bool):
    self.enforceWhitelist = enforce