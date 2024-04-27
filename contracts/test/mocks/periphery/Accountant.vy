# @version 0.3.7

from vyper.interfaces import ERC20

# INTERFACES #
struct StrategyParams:
    activation: uint256
    lastReport: uint256
    currentDebt: uint256
    maxDebt: uint256

interface IVault:
    def strategies(strategy: address) -> StrategyParams: view
    def asset() -> address: view

# EVENTS #
event CommitFeeManager:
    feeManager: address

event ApplyFeeManager:
    feeManager: address

event UpdatePerformanceFee:
    performanceFee: uint256

event UpdateManagementFee:
    managementFee: uint256

event UpdateRefundRatio:
    refundRatio: uint256

event DistributeRewards:
    rewards: uint256


# STRUCTS #
struct Fee:
    managementFee: uint256
    performanceFee: uint256


# CONSTANTS #
MAX_BPS: constant(uint256) = 10_000
MAX_SHARE: constant(uint256) = 7_500
# NOTE: A four-century period will be missing 3 of its 100 Julian leap years, leaving 97.
#       So the average year has 365 + 97/400 = 365.2425 days
#       ERROR(Julian): -0.0078
#       ERROR(Gregorian): -0.0003
#       A day = 24 * 60 * 60 sec = 86400 sec
#       365.2425 * 86400 = 31556952.0
SECS_PER_YEAR: constant(uint256) = 31_556_952  # 365.2425 days


# STORAGE #
feeManager: public(address)
futureFeeManager: public(address)
fees: public(HashMap[address, Fee])
refundRatios: public(HashMap[address, uint256])
asset: public(address)


@external
def __init__(asset: address):
    self.feeManager = msg.sender
    self.asset = asset


@external
def report(strategy: address, gain: uint256, loss: uint256) -> (uint256, uint256):
    """ """
    totalRefunds: uint256 = 0

    # managementFee is charged in both profit and loss scenarios
    strategyParams: StrategyParams = IVault(msg.sender).strategies(strategy)
    fee: Fee = self.fees[strategy]
    duration: uint256 = block.timestamp - strategyParams.lastReport

    #managementFee
    totalFees: uint256 = (
        (strategyParams.currentDebt)
        * duration
        * fee.managementFee
        / MAX_BPS
        / SECS_PER_YEAR
    )

    if gain > 0:
        totalFees += (gain * fee.performanceFee) / MAX_BPS
        # ensure fee does not exceed more than 75% of gain
        maximumFee: uint256 = (gain * MAX_SHARE) / MAX_BPS
        # test with min?
        if totalFees > maximumFee:
            return (maximumFee, 0)
    else:
        # Now taking loss from its own funds. In the future versions could be from different mechanisms
        assetBalance: uint256= ERC20(self.asset).balanceOf(self)
        refundRatio: uint256 = self.refundRatios[strategy]
        totalRefunds = loss * refundRatio / MAX_BPS
        if totalRefunds > 0:
            # TODO: permissions implications. msg.sender should only be vault
            self.erc20SafeApprove(IVault(self.asset).asset(), msg.sender, totalRefunds)
        
    return (totalFees, totalRefunds)

@internal
def erc20SafeApprove(token: address, spender: address, amount: uint256):
    # Used only to send tokens that are not the type managed by this Vault.
    # HACK: Used to handle non-compliant tokens like USDT
    response: Bytes[32] = raw_call(
        token,
        concat(
            method_id("approve(address,uint256)"),
            convert(spender, bytes32),
            convert(amount, bytes32),
        ),
        max_outsize=32,
    )
    if len(response) > 0:
        assert convert(response, bool), "Transfer failed!"


@external
def distribute(vault: ERC20):
    assert msg.sender == self.feeManager, "not fee manager"
    rewards: uint256 = vault.balanceOf(self)
    vault.transfer(msg.sender, rewards)
    log DistributeRewards(rewards)


@external
def setPerformanceFee(strategy: address, performanceFee: uint256):
    assert msg.sender == self.feeManager, "not fee manager"
    assert performanceFee <= self._performanceFeeThreshold(), "exceeds performance fee threshold"
    self.fees[strategy].performanceFee = performanceFee
    log UpdatePerformanceFee(performanceFee)


@external
def setManagementFee(strategy: address, managementFee: uint256):
    assert msg.sender == self.feeManager, "not fee manager"
    assert managementFee <= self._managementFeeThreshold(), "exceeds management fee threshold"
    self.fees[strategy].managementFee = managementFee
    log UpdateManagementFee(managementFee)


@external
def setRefundRatio(strategy: address, refundRatio: uint256):
    assert msg.sender == self.feeManager, "not fee manager"
    self.refundRatios[strategy] = refundRatio
    log UpdateRefundRatio(refundRatio)


@external
def commitFeeManager(futureFeeManager: address):
    assert msg.sender == self.feeManager, "not fee manager"
    self.futureFeeManager = futureFeeManager
    log CommitFeeManager(futureFeeManager)


@external
def applyFeeManager():
    assert msg.sender == self.feeManager, "not fee manager"
    assert self.futureFeeManager != ZERO_ADDRESS, "future fee manager != zero address"
    futureFeeManager: address = self.futureFeeManager
    self.feeManager = futureFeeManager
    log ApplyFeeManager(futureFeeManager)


@view
@external
def performanceFeeThreshold() -> uint256:
    return self._performanceFeeThreshold()


@view
@internal
def _performanceFeeThreshold() -> uint256:
    return MAX_BPS / 2


@view
@external
def managementFeeThreshold() -> uint256:
    return self._managementFeeThreshold()


@view
@internal
def _managementFeeThreshold() -> uint256:
    return MAX_BPS
