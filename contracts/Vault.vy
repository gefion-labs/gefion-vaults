# @version 0.3.7

"""
@title Gefion Vault
@license GNU AGPLv3
@author gefion.finance
@notice
    The Gefion Vault is designed as a non-opinionated system to distribute funds of 
    depositors for a specific `asset` into different opportunities (aka Strategies)
    and manage accounting in a robust way.

    Depositors receive shares (aka vaults tokens) proportional to their deposit amount. 
    Vault tokens are yield-bearing and can be redeemed at any time to get back deposit 
    plus any yield generated.

    Addresses that are given different permissioned roles by the `roleManager` 
    are then able to allocate funds as they best see fit to different strategies 
    and adjust the strategies and allocations as needed, as well as reporting realized
    profits or losses.

    Strategies are any ERC-4626 compliant contracts that use the same underlying `asset` 
    as the vault. The vault provides no assurances as to the safety of any strategy
    and it is the responsibility of those that hold the corresponding roles to choose
    and fund strategies that best fit their desired specifications.

    Those holding vault tokens are able to redeem the tokens for the corresponding
    amount of underlying asset based on any reported profits or losses since their
    initial deposit.

    The vault is built to be customized by the management to be able to fit their
    specific desired needs. Including the customization of strategies, accountants, 
    ownership etc.
"""

# INTERFACES #

from vyper.interfaces import ERC20
from vyper.interfaces import ERC20Detailed

interface IStrategy:
    def asset() -> address: view
    def balanceOf(owner: address) -> uint256: view
    def convertToAssets(shares: uint256) -> uint256: view
    def convertToShares(assets: uint256) -> uint256: view
    def previewWithdraw(assets: uint256) -> uint256: view
    def maxDeposit(receiver: address) -> uint256: view
    def deposit(assets: uint256, receiver: address) -> uint256: nonpayable
    def maxRedeem(owner: address) -> uint256: view
    def redeem(shares: uint256, receiver: address, owner: address) -> uint256: nonpayable
    
interface IAccountant:
    def report(strategy: address, gain: uint256, loss: uint256) -> (uint256, uint256): nonpayable

interface IDepositLimitModule:
    def availableDepositLimit(receiver: address) -> uint256: view
    
interface IWithdrawLimitModule:
    def availableWithdrawLimit(owner: address, maxLoss: uint256, strategies: DynArray[address, MAX_QUEUE]) -> uint256: view

interface IFactory:
    def protocolFeeConfig() -> (uint16, address): view

# EVENTS #
# ERC4626 EVENTS
event Deposit:
    sender: indexed(address)
    owner: indexed(address)
    assets: uint256
    shares: uint256

event Withdraw:
    sender: indexed(address)
    receiver: indexed(address)
    owner: indexed(address)
    assets: uint256
    shares: uint256

# ERC20 EVENTS
event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256

event Approval:
    owner: indexed(address)
    spender: indexed(address)
    value: uint256

# STRATEGY EVENTS
event StrategyChanged:
    strategy: indexed(address)
    changeType: indexed(StrategyChangeType)
    
event StrategyReported:
    strategy: indexed(address)
    gain: uint256
    loss: uint256
    currentDebt: uint256
    protocolFees: uint256
    totalFees: uint256
    totalRefunds: uint256

# DEBT MANAGEMENT EVENTS
event DebtUpdated:
    strategy: indexed(address)
    currentDebt: uint256
    newDebt: uint256

# ROLE UPDATES
event RoleSet:
    account: indexed(address)
    role: indexed(Roles)

# STORAGE MANAGEMENT EVENTS
event UpdateRoleManager:
    roleManager: indexed(address)

event UpdateAccountant:
    accountant: indexed(address)

event UpdateDepositLimitModule:
    depositLimitModule: indexed(address)

event UpdateWithdrawLimitModule:
    withdrawLimitModule: indexed(address)

event UpdateDefaultQueue:
    newDefaultQueue: DynArray[address, MAX_QUEUE]

event UpdateUseDefaultQueue:
    useDefaultQueue: bool

event UpdatedMaxDebtForStrategy:
    sender: indexed(address)
    strategy: indexed(address)
    newDebt: uint256

event UpdateDepositLimit:
    depositLimit: uint256

event UpdateMinimumTotalIdle:
    minimumTotalIdle: uint256

event UpdateProfitMaxUnlockTime:
    profitMaxUnlockTime: uint256

event DebtPurchased:
    strategy: indexed(address)
    amount: uint256

event Shutdown:
    pass

# STRUCTS #
struct StrategyParams:
    # Timestamp when the strategy was added.
    activation: uint256 
    # Timestamp of the strategies last report.
    lastReport: uint256
    # The current assets the strategy holds.
    currentDebt: uint256
    # The max assets the strategy can hold. 
    maxDebt: uint256

# CONSTANTS #
# The max length the withdrawal queue can be.
MAX_QUEUE: constant(uint256) = 10
# 100% in Basis Points.
MAX_BPS: constant(uint256) = 10_000
# Extended for profit locking calculations.
MAX_BPS_EXTENDED: constant(uint256) = 1_000_000_000_000
# The version of this vault.
API_VERSION: constant(String[28]) = "1.0.0"

# ENUMS #
# Each permissioned function has its own Role.
# Roles can be combined in any combination or all kept separate.
# Follows python Enum patterns so the first Enum == 1 and doubles each time.
enum Roles:
    ADD_STRATEGY_MANAGER # Can add strategies to the vault.
    REVOKE_STRATEGY_MANAGER # Can remove strategies from the vault.
    FORCE_REVOKE_MANAGER # Can force remove a strategy causing a loss.
    ACCOUNTANT_MANAGER # Can set the accountant that assess fees.
    QUEUE_MANAGER # Can set the default withdrawal queue.
    REPORTING_MANAGER # Calls report for strategies.
    DEBT_MANAGER # Adds and removes debt from strategies.
    MAX_DEBT_MANAGER # Can set the max debt for a strategy.
    DEPOSIT_LIMIT_MANAGER # Sets deposit limit and module for the vault.
    WITHDRAW_LIMIT_MANAGER # Sets the withdraw limit module.
    MINIMUM_IDLE_MANAGER # Sets the minimum total idle the vault should keep.
    PROFIT_UNLOCK_MANAGER # Sets the profitMaxUnlockTime.
    DEBT_PURCHASER # Can purchase bad debt from the vault.
    EMERGENCY_MANAGER # Can shutdown vault in an emergency.

enum StrategyChangeType:
    ADDED
    REVOKED

enum Rounding:
    ROUND_DOWN
    ROUND_UP

# STORAGE #
# Underlying token used by the vault.
asset: public(address)
# Based off the `asset` decimals.
decimals: public(uint8)
# Deployer contract used to retrieve the protocol fee config.
factory: address

# HashMap that records all the strategies that are allowed to receive assets from the vault.
strategies: public(HashMap[address, StrategyParams])
# The current default withdrawal queue.
defaultQueue: public(DynArray[address, MAX_QUEUE])
# Should the vault use the defaultQueue regardless whats passed in.
useDefaultQueue: public(bool)

### ACCOUNTING ###
# ERC20 - amount of shares per account
_balanceOf: HashMap[address, uint256]
# ERC20 - owner -> (spender -> amount)
allowance: public(HashMap[address, HashMap[address, uint256]])
# Total amount of shares that are currently minted including those locked.
_totalSupply: uint256
# Total amount of assets that has been deposited in strategies.
_totalDebt: uint256
# Current assets held in the vault contract. Replacing balanceOf(this) to avoid pricePerShare manipulation.
_totalIdle: uint256
# Minimum amount of assets that should be kept in the vault contract to allow for fast, cheap redeems.
minimumTotalIdle: public(uint256)
# Maximum amount of tokens that the vault can accept. If totalAssets > depositLimit, deposits will revert.
depositLimit: public(uint256)

### PERIPHERY ###
# Contract that charges fees and can give refunds.
accountant: public(address)
# Contract to control the deposit limit.
depositLimitModule: public(address)
# Contract to control the withdraw limit.
withdrawLimitModule: public(address)

### ROLES ###
# HashMap mapping addresses to their roles
roles: public(HashMap[address, Roles])
# Address that can add and remove roles to addresses.
roleManager: public(address)
# Temporary variable to store the address of the next roleManager until the role is accepted.
futureRoleManager: public(address)

# ERC20 - name of the vaults token.
name: public(String[64])
# ERC20 - symbol of the vaults token.
symbol: public(String[32])

# State of the vault - if set to true, only withdrawals will be available. It can't be reverted.
shutdown: bool
# The amount of time profits will unlock over.
_profitMaxUnlockTime: uint256
# The timestamp of when the current unlocking period ends.
_fullProfitUnlockDate: uint256
# The per second rate at which profit will unlock.
_profitUnlockingRate: uint256
# Last timestamp of the most recent profitable report.
_lastProfitUpdate: uint256

# `nonces` track `permit` approvals with signature.
nonces: public(HashMap[address, uint256])
DOMAIN_TYPE_HASH: constant(bytes32) = keccak256('EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)')
PERMIT_TYPE_HASH: constant(bytes32) = keccak256("Permit(address owner,address spender,uint256 value,uint256 nonce,uint256 deadline)")

# Constructor
@external
def __init__():
    # Set `asset` so it cannot be re-initialized.
    self.asset = self
    
@external
def initialize(
    asset: address, 
    name: String[64], 
    symbol: String[32], 
    roleManager: address, 
    profitMaxUnlockTime: uint256
):
    """
    @notice
        Initialize a new vault. Sets the asset, name, symbol, and role manager.
    @param asset
        The address of the asset that the vault will accept.
    @param name
        The name of the vault token.
    @param symbol
        The symbol of the vault token.
    @param roleManager 
        The address that can add and remove roles to addresses
    @param profitMaxUnlockTime
        The amount of time that the profit will be locked for
    """
    assert self.asset == empty(address), "initialized"
    assert asset != empty(address), "ZERO ADDRESS"
    assert roleManager != empty(address), "ZERO ADDRESS"

    self.asset = asset
    # Get the decimals for the vault to use.
    self.decimals = ERC20Detailed(asset).decimals()
    
    # Set the factory as the deployer address.
    self.factory = msg.sender

    # Must be less than one year for report cycles
    assert profitMaxUnlockTime <= 31_556_952 # dev: profit unlock time too long
    self._profitMaxUnlockTime = profitMaxUnlockTime

    self.name = name
    self.symbol = symbol
    self.roleManager = roleManager

## SHARE MANAGEMENT ##
## ERC20 ##
@internal
def _spendAllowance(owner: address, spender: address, amount: uint256):
    # Unlimited approval does nothing (saves an SSTORE)
    currentAllowance: uint256 = self.allowance[owner][spender]
    if (currentAllowance < max_value(uint256)):
        assert currentAllowance >= amount, "insufficient allowance"
        self._approve(owner, spender, unsafe_sub(currentAllowance, amount))

@internal
def _transfer(sender: address, receiver: address, amount: uint256):
    senderBalance: uint256 = self._balanceOf[sender]
    assert senderBalance >= amount, "insufficient funds"
    self._balanceOf[sender] = unsafe_sub(senderBalance, amount)
    self._balanceOf[receiver] = unsafe_add(self._balanceOf[receiver], amount)
    log Transfer(sender, receiver, amount)

@internal
def _transferFrom(sender: address, receiver: address, amount: uint256) -> bool:
    self._spendAllowance(sender, msg.sender, amount)
    self._transfer(sender, receiver, amount)
    return True

@internal
def _approve(owner: address, spender: address, amount: uint256) -> bool:
    self.allowance[owner][spender] = amount
    log Approval(owner, spender, amount)
    return True

@internal
def _permit(
    owner: address, 
    spender: address, 
    amount: uint256, 
    deadline: uint256, 
    v: uint8, 
    r: bytes32, 
    s: bytes32
) -> bool:
    assert owner != empty(address), "invalid owner"
    assert deadline >= block.timestamp, "permit expired"
    nonce: uint256 = self.nonces[owner]
    digest: bytes32 = keccak256(
        concat(
            b'\x19\x01',
            self.domainSeparator(),
            keccak256(
                concat(
                    PERMIT_TYPE_HASH,
                    convert(owner, bytes32),
                    convert(spender, bytes32),
                    convert(amount, bytes32),
                    convert(nonce, bytes32),
                    convert(deadline, bytes32),
                )
            )
        )
    )
    assert ecrecover(
        digest, v, r, s
    ) == owner, "invalid signature"

    self.allowance[owner][spender] = amount
    self.nonces[owner] = nonce + 1
    log Approval(owner, spender, amount)
    return True

@internal
def _burnShares(shares: uint256, owner: address):
    self._balanceOf[owner] -= shares
    self._totalSupply = unsafe_sub(self._totalSupply, shares)
    log Transfer(owner, empty(address), shares)

@view
@internal
def _unlockedShares() -> uint256:
    """
    Returns the amount of shares that have been unlocked.
    To avoid sudden pricePerShare spikes, profits can be processed 
    through an unlocking period. The mechanism involves shares to be 
    minted to the vault which are unlocked gradually over time. Shares 
    that have been locked are gradually unlocked over profitMaxUnlockTime.
    """
    _fullProfitUnlockDate: uint256 = self._fullProfitUnlockDate
    unlockedShares: uint256 = 0
    if _fullProfitUnlockDate > block.timestamp:
        # If we have not fully unlocked, we need to calculate how much has been.
        unlockedShares = self._profitUnlockingRate * (block.timestamp - self._lastProfitUpdate) / MAX_BPS_EXTENDED

    elif _fullProfitUnlockDate != 0:
        # All shares have been unlocked
        unlockedShares = self._balanceOf[self]

    return unlockedShares


@view
@internal
def _totalLockedSupply() -> uint256:
    # Need to account for the shares issued to the vault that have unlocked.
    return self._totalSupply - self._unlockedShares()

@view
@internal
def _totalAssets() -> uint256:
    """
    Total amount of assets that are in the vault and in the strategies. 
    """
    return self._totalIdle + self._totalDebt

@view
@internal
def _convertToAssets(shares: uint256, rounding: Rounding) -> uint256:
    """ 
    assets = shares * (totalAssets / totalSupply) --- (== pricePerShare * shares)
    """
    if shares == max_value(uint256) or shares == 0:
        return shares

    totalSupply: uint256 = self._totalLockedSupply()
    # if totalSupply is 0, pricePerShare is 1
    if totalSupply == 0: 
        return shares

    numerator: uint256 = shares * self._totalAssets()
    amount: uint256 = numerator / totalSupply
    if rounding == Rounding.ROUND_UP and numerator % totalSupply != 0:
        amount += 1

    return amount

@view
@internal
def _convertToShares(assets: uint256, rounding: Rounding) -> uint256:
    """
    shares = amount * (totalSupply / totalAssets) --- (== amount / pricePerShare)
    """
    if assets == max_value(uint256) or assets == 0:
        return assets

    totalSupply: uint256 = self._totalLockedSupply()
    totalAssets: uint256 = self._totalAssets()

    if totalAssets == 0:
        # if totalAssets and totalSupply is 0, pricePerShare is 1
        if totalSupply == 0:
            return assets
        else:
            # Else if totalSupply > 0 pricePerShare is 0
            return 0

    numerator: uint256 = assets * totalSupply
    shares: uint256 = numerator / totalAssets
    if rounding == Rounding.ROUND_UP and numerator % totalAssets != 0:
        shares += 1

    return shares

@internal
def _erc20SafeApprove(token: address, spender: address, amount: uint256):
    # Used only to approve tokens that are not the type managed by this Vault.
    # Used to handle non-compliant tokens like USDT
    assert ERC20(token).approve(spender, amount, default_return_value=True), "approval failed"

@internal
def _erc20SafeTransferFrom(token: address, sender: address, receiver: address, amount: uint256):
    # Used only to transfer tokens that are not the type managed by this Vault.
    # Used to handle non-compliant tokens like USDT
    assert ERC20(token).transferFrom(sender, receiver, amount, default_return_value=True), "transfer failed"

@internal
def _erc20SafeTransfer(token: address, receiver: address, amount: uint256):
    # Used only to send tokens that are not the type managed by this Vault.
    # Used to handle non-compliant tokens like USDT
    assert ERC20(token).transfer(receiver, amount, default_return_value=True), "transfer failed"

@internal
def _issueShares(shares: uint256, recipient: address):
    self._balanceOf[recipient] = unsafe_add(self._balanceOf[recipient], shares)
    self._totalSupply += shares

    log Transfer(empty(address), recipient, shares)

@internal
def _issueSharesForAmount(amount: uint256, recipient: address) -> uint256:
    """
    Issues shares that are worth 'amount' in the underlying token (asset).
    WARNING: this takes into account that any new assets have been summed 
    to totalAssets (otherwise pps will go down).
    """
    totalSupply: uint256 = self._totalLockedSupply()
    totalAssets: uint256 = self._totalAssets()
    newShares: uint256 = 0
    
    # If no supply PPS = 1.
    if totalSupply == 0:
        newShares = amount
    elif totalAssets > amount:
        newShares = amount * totalSupply / (totalAssets - amount)

    # We don't make the function revert
    if newShares == 0:
       return 0

    self._issueShares(newShares, recipient)

    return newShares

## ERC4626 ##
@view
@internal
def _maxDeposit(receiver: address) -> uint256: 
    if receiver in [empty(address), self]:
        return 0

    # If there is a deposit limit module set use that.
    depositLimitModule: address = self.depositLimitModule
    if depositLimitModule != empty(address):
        return IDepositLimitModule(depositLimitModule).availableDepositLimit(receiver)
    
    # Else use the standard flow.
    _depositLimit: uint256 = self.depositLimit
    if (_depositLimit == max_value(uint256)):
        return _depositLimit

    _totalAssets: uint256 = self._totalAssets()
    if (_totalAssets >= _depositLimit):
        return 0

    return unsafe_sub(_depositLimit, _totalAssets)

@view
@internal
def _maxWithdraw(
    owner: address,
    maxLoss: uint256,
    strategies: DynArray[address, MAX_QUEUE]
) -> uint256:
    """
    @dev Returns the max amount of `asset` an `owner` can withdraw.

    This will do a full simulation of the withdraw in order to determine
    how much is currently liquid and if the `maxLoss` would allow for the 
    tx to not revert.

    This will track any expected loss to check if the tx will revert, but
    not account for it in the amount returned since it is unrealised and 
    therefore will not be accounted for in the conversion rates.

    i.e. If we have 100 debt and 10 of unrealised loss, the max we can get
    out is 90, but a user of the vault will need to call withdraw with 100
    in order to get the full 90 out.
    """

    # Get the max amount for the owner if fully liquid.
    maxAssets: uint256 = self._convertToAssets(self._balanceOf[owner], Rounding.ROUND_DOWN)

    # If there is a withdraw limit module use that.
    withdrawLimitModule: address = self.withdrawLimitModule
    if withdrawLimitModule != empty(address):
        return min(
            # Use the min between the returned value and the max.
            # Means the limit module doesn't need to account for balances or conversions.
            IWithdrawLimitModule(withdrawLimitModule).availableWithdrawLimit(owner, maxLoss, strategies),
            maxAssets
        )
    
    # See if we have enough idle to service the withdraw.
    currentIdle: uint256 = self._totalIdle
    if maxAssets > currentIdle:
        # Track how much we can pull.
        have: uint256 = currentIdle
        loss: uint256 = 0

        # Cache the default queue.
        _strategies: DynArray[address, MAX_QUEUE] = self.defaultQueue

        # If a custom queue was passed, and we don't force the default queue.
        if len(strategies) != 0 and not self.useDefaultQueue:
            # Use the custom queue.
            _strategies = strategies

        for strategy in _strategies:
            # Can't use an invalid strategy.
            assert self.strategies[strategy].activation != 0, "inactive strategy"

            # Get the maximum amount the vault would withdraw from the strategy.
            toWithdraw: uint256 = min(
                # What we still need for the full withdraw.
                maxAssets - have, 
                # The current debt the strategy has.
                self.strategies[strategy].currentDebt
            )

            # Get any unrealised loss for the strategy.
            unrealisedLoss: uint256 = self._assessShareOfUnrealisedLosses(strategy, toWithdraw)

            # See if any limit is enforced by the strategy.
            strategyLimit: uint256 = IStrategy(strategy).convertToAssets(
                IStrategy(strategy).maxRedeem(self)
            )

            # Adjust accordingly if there is a max withdraw limit.
            realizableWithdraw: uint256 = toWithdraw - unrealisedLoss
            if strategyLimit < realizableWithdraw:
                if unrealisedLoss != 0:
                    # lower unrealised loss proportional to the limit.
                    unrealisedLoss = unrealisedLoss * strategyLimit / realizableWithdraw

                # Still count the unrealised loss as withdrawable.
                toWithdraw = strategyLimit + unrealisedLoss
                
            # If 0 move on to the next strategy.
            if toWithdraw == 0:
                continue

            # If there would be a loss with a non-maximum `maxLoss` value.
            if unrealisedLoss > 0 and maxLoss < MAX_BPS:
                # Check if the loss is greater than the allowed range.
                if loss + unrealisedLoss > (have + toWithdraw) * maxLoss / MAX_BPS:
                    # If so use the amounts up till now.
                    break

            # Add to what we can pull.
            have += toWithdraw

            # If we have all we need break.
            if have >= maxAssets:
                break

            # Add any unrealised loss to the total
            loss += unrealisedLoss

        # Update the max after going through the queue.
        # In case we broke early or exhausted the queue.
        maxAssets = have

    return maxAssets

@internal
def _deposit(sender: address, recipient: address, assets: uint256) -> uint256:
    """
    Used for `deposit` calls to transfer the amount of `asset` to the vault, 
    issue the corresponding shares to the `recipient` and update all needed 
    vault accounting.
    """
    assert self.shutdown == False # dev: shutdown
    assert assets <= self._maxDeposit(recipient), "exceed deposit limit"
 
    # Transfer the tokens to the vault first.
    self._erc20SafeTransferFrom(self.asset, msg.sender, self, assets)
    # Record the change in total assets.
    self._totalIdle += assets
    
    # Issue the corresponding shares for assets.
    shares: uint256 = self._issueSharesForAmount(assets, recipient)

    assert shares > 0, "cannot mint zero"

    log Deposit(sender, recipient, assets, shares)
    return shares

@internal
def _mint(sender: address, recipient: address, shares: uint256) -> uint256:
    """
    Used for `mint` calls to issue the corresponding shares to the `recipient`,
    transfer the amount of `asset` to the vault, and update all needed vault 
    accounting.
    """
    assert self.shutdown == False # dev: shutdown
    # Get corresponding amount of assets.
    assets: uint256 = self._convertToAssets(shares, Rounding.ROUND_UP)

    assert assets > 0, "cannot deposit zero"
    assert assets <= self._maxDeposit(recipient), "exceed deposit limit"

    # Transfer the tokens to the vault first.
    self._erc20SafeTransferFrom(self.asset, msg.sender, self, assets)
    # Record the change in total assets.
    self._totalIdle += assets
    
    # Issue the corresponding shares for assets.
    self._issueShares(shares, recipient)

    log Deposit(sender, recipient, assets, shares)
    return assets

@view
@internal
def _assessShareOfUnrealisedLosses(strategy: address, assetsNeeded: uint256) -> uint256:
    """
    Returns the share of losses that a user would take if withdrawing from this strategy
    This accounts for losses that have been realized at the strategy level but not yet
    realized at the vault level.

    e.g. if the strategy has unrealised losses for 10% of its current debt and the user 
    wants to withdraw 1_000 tokens, the losses that they will take is 100 token
    """
    # Minimum of how much debt the debt should be worth.
    strategyCurrentDebt: uint256 = self.strategies[strategy].currentDebt
    # The actual amount that the debt is currently worth.
    vaultShares: uint256 = IStrategy(strategy).balanceOf(self)
    strategyAssets: uint256 = IStrategy(strategy).convertToAssets(vaultShares)
    
    # If no losses, return 0
    if strategyAssets >= strategyCurrentDebt or strategyCurrentDebt == 0:
        return 0

    # Users will withdraw assetsNeeded divided by loss ratio (strategyAssets / strategyCurrentDebt - 1).
    # NOTE: If there are unrealised losses, the user will take his share.
    numerator: uint256 = assetsNeeded * strategyAssets
    usersShareOfLoss: uint256 = assetsNeeded - numerator / strategyCurrentDebt
    # Always round up.
    if numerator % strategyCurrentDebt != 0:
        usersShareOfLoss += 1

    return usersShareOfLoss

@internal
def _withdrawFromStrategy(strategy: address, assetsToWithdraw: uint256):
    """
    This takes the amount denominated in asset and performs a {redeem}
    with the corresponding amount of shares.

    We use {redeem} to natively take on losses without additional non-4626 standard parameters.
    """
    # Need to get shares since we use redeem to be able to take on losses.
    sharesToRedeem: uint256 = min(
        # Use previewWithdraw since it should round up.
        IStrategy(strategy).previewWithdraw(assetsToWithdraw), 
        # And check against our actual balance.
        IStrategy(strategy).balanceOf(self)
    )
    # Redeem the shares.
    IStrategy(strategy).redeem(sharesToRedeem, self, self)

@internal
def _redeem(
    sender: address, 
    receiver: address, 
    owner: address,
    assets: uint256,
    shares: uint256, 
    maxLoss: uint256,
    strategies: DynArray[address, MAX_QUEUE]
) -> uint256:
    """
    This will attempt to free up the full amount of assets equivalent to
    `shares` and transfer them to the `receiver`. If the vault does
    not have enough idle funds it will go through any strategies provided by
    either the withdrawer or the defaultQueue to free up enough funds to 
    service the request.

    The vault will attempt to account for any unrealized losses taken on from
    strategies since their respective last reports.

    Any losses realized during the withdraw from a strategy will be passed on
    to the user that is redeeming their vault shares unless it exceeds the given
    `maxLoss`.
    """
    assert receiver != empty(address), "ZERO ADDRESS"
    assert shares > 0, "no shares to redeem"
    assert assets > 0, "no assets to withdraw"
    assert maxLoss <= MAX_BPS, "max loss"
    
    # If there is a withdraw limit module, check the max.
    withdrawLimitModule: address = self.withdrawLimitModule
    if withdrawLimitModule != empty(address):
        assert assets <= IWithdrawLimitModule(withdrawLimitModule).availableWithdrawLimit(owner, maxLoss, strategies), "exceed withdraw limit"

    assert self._balanceOf[owner] >= shares, "insufficient shares to redeem"
    
    if sender != owner:
        self._spendAllowance(owner, sender, shares)

    # The amount of the underlying token to withdraw.
    requestedAssets: uint256 = assets

    # load to memory to save gas
    currentTotalIdle: uint256 = self._totalIdle
    _asset: address = self.asset

    # If there are not enough assets in the Vault contract, we try to free
    # funds from strategies.
    if requestedAssets > currentTotalIdle:

        # Cache the default queue.
        _strategies: DynArray[address, MAX_QUEUE] = self.defaultQueue

        # If a custom queue was passed, and we don't force the default queue.
        if len(strategies) != 0 and not self.useDefaultQueue:
            # Use the custom queue.
            _strategies = strategies

        # load to memory to save gas
        currentTotalDebt: uint256 = self._totalDebt

        # Withdraw from strategies only what idle doesn't cover.
        # `assetsNeeded` is the total amount we need to fill the request.
        assetsNeeded: uint256 = unsafe_sub(requestedAssets, currentTotalIdle)
        # `assetsToWithdraw` is the amount to request from the current strategy.
        assetsToWithdraw: uint256 = 0

        # To compare against real withdrawals from strategies
        previousBalance: uint256 = ERC20(_asset).balanceOf(self)

        for strategy in _strategies:
            # Make sure we have a valid strategy.
            assert self.strategies[strategy].activation != 0, "inactive strategy"

            # How much should the strategy have.
            currentDebt: uint256 = self.strategies[strategy].currentDebt

            # What is the max amount to withdraw from this strategy.
            assetsToWithdraw = min(assetsNeeded, currentDebt)

            # Cache maxWithdraw now for use if unrealized loss > 0
            # Use maxRedeem and convert it since we use redeem.
            maxWithdraw: uint256 = IStrategy(strategy).convertToAssets(
                IStrategy(strategy).maxRedeem(self)
            )

            # CHECK FOR UNREALISED LOSSES
            # If unrealised losses > 0, then the user will take the proportional share 
            # and realize it (required to avoid users withdrawing from lossy strategies).
            # NOTE: strategies need to manage the fact that realising part of the loss can 
            # mean the realisation of 100% of the loss!! (i.e. if for withdrawing 10% of the
            # strategy it needs to unwind the whole position, generated losses might be bigger)
            unrealisedLossesShare: uint256 = self._assessShareOfUnrealisedLosses(strategy, assetsToWithdraw)
            if unrealisedLossesShare > 0:
                # If max withdraw is limiting the amount to pull, we need to adjust the portion of 
                # the unrealized loss the user should take.
                if maxWithdraw < assetsToWithdraw - unrealisedLossesShare:
                    # How much would we want to withdraw
                    wanted: uint256 = assetsToWithdraw - unrealisedLossesShare
                    # Get the proportion of unrealised comparing what we want vs. what we can get
                    unrealisedLossesShare = unrealisedLossesShare * maxWithdraw / wanted
                    # Adjust assetsToWithdraw so all future calculations work correctly
                    assetsToWithdraw = maxWithdraw + unrealisedLossesShare
                
                # User now "needs" less assets to be unlocked (as he took some as losses)
                assetsToWithdraw -= unrealisedLossesShare
                requestedAssets -= unrealisedLossesShare
                # NOTE: done here instead of waiting for regular update of these values 
                # because it's a rare case (so we can save minor amounts of gas)
                assetsNeeded -= unrealisedLossesShare
                currentTotalDebt -= unrealisedLossesShare

                # If max withdraw is 0 and unrealised loss is still > 0 then the strategy likely
                # realized a 100% loss and we will need to realize that loss before moving on.
                if maxWithdraw == 0 and unrealisedLossesShare > 0:
                    # Adjust the strategy debt accordingly.
                    newDebt: uint256 = currentDebt - unrealisedLossesShare
        
                    # Update strategies storage
                    self.strategies[strategy].currentDebt = newDebt
                    # Log the debt update
                    log DebtUpdated(strategy, currentDebt, newDebt)

            # Adjust based on the max withdraw of the strategy.
            assetsToWithdraw = min(assetsToWithdraw, maxWithdraw)

            # Can't withdraw 0.
            if assetsToWithdraw == 0:
                continue
            
            # WITHDRAW FROM STRATEGY
            self._withdrawFromStrategy(strategy, assetsToWithdraw)
            postBalance: uint256 = ERC20(_asset).balanceOf(self)
            
            # Always check against the real amounts.
            withdrawn: uint256 = postBalance - previousBalance
            loss: uint256 = 0
            # Check if we redeemed too much.
            if withdrawn > assetsToWithdraw:
                # Make sure we don't underflow in debt updates.
                if withdrawn > currentDebt:
                    # Can't withdraw more than our debt.
                    assetsToWithdraw = currentDebt
                else:
                    # Add the extra to how much we withdrew.
                    assetsToWithdraw += (unsafe_sub(withdrawn, assetsToWithdraw))

            # If we have not received what we expected, we consider the difference a loss.
            elif withdrawn < assetsToWithdraw:
                loss = unsafe_sub(assetsToWithdraw, withdrawn)

            # NOTE: strategy's debt decreases by the full amount but the total idle increases 
            # by the actual amount only (as the difference is considered lost).
            currentTotalIdle += (assetsToWithdraw - loss)
            requestedAssets -= loss
            currentTotalDebt -= assetsToWithdraw

            # Vault will reduce debt because the unrealised loss has been taken by user
            newDebt: uint256 = currentDebt - (assetsToWithdraw + unrealisedLossesShare)
        
            # Update strategies storage
            self.strategies[strategy].currentDebt = newDebt
            # Log the debt update
            log DebtUpdated(strategy, currentDebt, newDebt)

            # Break if we have enough total idle to serve initial request.
            if requestedAssets <= currentTotalIdle:
                break

            # We update the previousBalance variable here to save gas in next iteration.
            previousBalance = postBalance

            # Reduce what we still need. Safe to use assetsToWithdraw 
            # here since it has been checked against requestedAssets
            assetsNeeded -= assetsToWithdraw

        # If we exhaust the queue and still have insufficient total idle, revert.
        assert currentTotalIdle >= requestedAssets, "insufficient assets in vault"
        # Commit memory to storage.
        self._totalDebt = currentTotalDebt

    # Check if there is a loss and a non-default value was set.
    if assets > requestedAssets and maxLoss < MAX_BPS:
        # Assure the loss is within the allowed range.
        assert assets - requestedAssets <= assets * maxLoss / MAX_BPS, "too much loss"

    # First burn the corresponding shares from the redeemer.
    self._burnShares(shares, owner)
    # Commit memory to storage.
    self._totalIdle = currentTotalIdle - requestedAssets
    # Transfer the requested amount to the receiver.
    self._erc20SafeTransfer(_asset, receiver, requestedAssets)

    log Withdraw(sender, receiver, owner, requestedAssets, shares)
    return requestedAssets

## STRATEGY MANAGEMENT ##
@internal
def _addStrategy(newStrategy: address, addToQueue: bool):
    assert newStrategy not in [self, empty(address)], "strategy cannot be zero address"
    assert IStrategy(newStrategy).asset() == self.asset, "invalid asset"
    assert self.strategies[newStrategy].activation == 0, "strategy already active"

    # Add the new strategy to the mapping.
    self.strategies[newStrategy] = StrategyParams({
        activation: block.timestamp,
        lastReport: block.timestamp,
        currentDebt: 0,
        maxDebt: 0
    })

    # If we are adding to the queue and the default queue has space, add the strategy.
    if addToQueue and len(self.defaultQueue) < MAX_QUEUE:
        self.defaultQueue.append(newStrategy)        
        
    log StrategyChanged(newStrategy, StrategyChangeType.ADDED)

@internal
def _revokeStrategy(strategy: address, force: bool=False):
    assert self.strategies[strategy].activation != 0, "strategy not active"

    # If force revoking a strategy, it will cause a loss.
    loss: uint256 = 0
    
    if self.strategies[strategy].currentDebt != 0:
        assert force, "strategy has debt"
        # Vault realizes the full loss of outstanding debt.
        loss = self.strategies[strategy].currentDebt
        # Adjust total vault debt.
        self._totalDebt -= loss

        log StrategyReported(strategy, 0, loss, 0, 0, 0, 0)

    # Set strategy params all back to 0 (WARNING: it can be re-added).
    self.strategies[strategy] = StrategyParams({
      activation: 0,
      lastReport: 0,
      currentDebt: 0,
      maxDebt: 0
    })

    # Remove strategy if it is in the default queue.
    newQueue: DynArray[address, MAX_QUEUE] = []
    for _strategy in self.defaultQueue:
        # Add all strategies to the new queue besides the one revoked.
        if _strategy != strategy:
            newQueue.append(_strategy)
        
    # Set the default queue to our updated queue.
    self.defaultQueue = newQueue

    log StrategyChanged(strategy, StrategyChangeType.REVOKED)

# DEBT MANAGEMENT #
@internal
def _updateDebt(strategy: address, targetDebt: uint256, maxLoss: uint256) -> uint256:
    """
    The vault will re-balance the debt vs target debt. Target debt must be
    smaller or equal to strategy's maxDebt. This function will compare the 
    current debt with the target debt and will take funds or deposit new 
    funds to the strategy. 

    The strategy can require a maximum amount of funds that it wants to receive
    to invest. The strategy can also reject freeing funds if they are locked.
    """
    # How much we want the strategy to have.
    newDebt: uint256 = targetDebt
    # How much the strategy currently has.
    currentDebt: uint256 = self.strategies[strategy].currentDebt

    # If the vault is shutdown we can only pull funds.
    if self.shutdown:
        newDebt = 0

    assert newDebt != currentDebt, "new debt equals current debt"

    if currentDebt > newDebt:
        # Reduce debt.
        assetsToWithdraw: uint256 = unsafe_sub(currentDebt, newDebt)

        # Ensure we always have minimumTotalIdle when updating debt.
        minimumTotalIdle: uint256 = self.minimumTotalIdle
        totalIdle: uint256 = self._totalIdle
        
        # Respect minimum total idle in vault
        if totalIdle + assetsToWithdraw < minimumTotalIdle:
            assetsToWithdraw = unsafe_sub(minimumTotalIdle, totalIdle)
            # Cant withdraw more than the strategy has.
            if assetsToWithdraw > currentDebt:
                assetsToWithdraw = currentDebt

        # Check how much we are able to withdraw.
        # Use maxRedeem and convert since we use redeem.
        withdrawable: uint256 = IStrategy(strategy).convertToAssets(
            IStrategy(strategy).maxRedeem(self)
        )
        assert withdrawable != 0, "nothing to withdraw"

        # If insufficient withdrawable, withdraw what we can.
        if withdrawable < assetsToWithdraw:
            assetsToWithdraw = withdrawable

        # If there are unrealised losses we don't let the vault reduce its debt until there is a new report
        unrealisedLossesShare: uint256 = self._assessShareOfUnrealisedLosses(strategy, assetsToWithdraw)
        assert unrealisedLossesShare == 0, "strategy has unrealised losses"
        
        # Cache for repeated use.
        _asset: address = self.asset

        # Always check the actual amount withdrawn.
        preBalance: uint256 = ERC20(_asset).balanceOf(self)
        self._withdrawFromStrategy(strategy, assetsToWithdraw)
        postBalance: uint256 = ERC20(_asset).balanceOf(self)
        
        # making sure we are changing idle according to the real result no matter what. 
        # We pull funds with {redeem} so there can be losses or rounding differences.
        withdrawn: uint256 = min(postBalance - preBalance, currentDebt)

        # If we didn't get the amount we asked for and there is a max loss.
        if withdrawn < assetsToWithdraw and maxLoss < MAX_BPS:
            # Make sure the loss is within the allowed range.
            assert assetsToWithdraw - withdrawn <= assetsToWithdraw * maxLoss / MAX_BPS, "too much loss"

        # If we got too much make sure not to increase PPS.
        elif withdrawn > assetsToWithdraw:
            assetsToWithdraw = withdrawn

        # Update storage.
        self._totalIdle += withdrawn # actual amount we got.
        # Amount we tried to withdraw in case of losses
        self._totalDebt -= assetsToWithdraw 

        newDebt = currentDebt - assetsToWithdraw
    else: 
        # We are increasing the strategies debt

        # Revert if targetDebt cannot be achieved due to configured maxDebt for given strategy
        assert newDebt <= self.strategies[strategy].maxDebt, "target debt higher than max debt"

        # Vault is increasing debt with the strategy by sending more funds.
        maxDeposit: uint256 = IStrategy(strategy).maxDeposit(self)
        assert maxDeposit != 0, "nothing to deposit"

        # Deposit the difference between desired and current.
        assetsToDeposit: uint256 = newDebt - currentDebt
        if assetsToDeposit > maxDeposit:
            # Deposit as much as possible.
            assetsToDeposit = maxDeposit
        
        # Ensure we always have minimumTotalIdle when updating debt.
        minimumTotalIdle: uint256 = self.minimumTotalIdle
        totalIdle: uint256 = self._totalIdle

        assert totalIdle > minimumTotalIdle, "no funds to deposit"
        availableIdle: uint256 = unsafe_sub(totalIdle, minimumTotalIdle)

        # If insufficient funds to deposit, transfer only what is free.
        if assetsToDeposit > availableIdle:
            assetsToDeposit = availableIdle

        # Can't Deposit 0.
        if assetsToDeposit > 0:
            # Cache for repeated use.
            _asset: address = self.asset

            # Approve the strategy to pull only what we are giving it.
            self._erc20SafeApprove(_asset, strategy, assetsToDeposit)

            # Always update based on actual amounts deposited.
            preBalance: uint256 = ERC20(_asset).balanceOf(self)
            IStrategy(strategy).deposit(assetsToDeposit, self)
            postBalance: uint256 = ERC20(_asset).balanceOf(self)

            # Make sure our approval is always back to 0.
            self._erc20SafeApprove(_asset, strategy, 0)

            # Making sure we are changing according to the real result no 
            # matter what. This will spend more gas but makes it more robust.
            assetsToDeposit = preBalance - postBalance

            # Update storage.
            self._totalIdle -= assetsToDeposit
            self._totalDebt += assetsToDeposit

        newDebt = currentDebt + assetsToDeposit

    # Commit memory to storage.
    self.strategies[strategy].currentDebt = newDebt

    log DebtUpdated(strategy, currentDebt, newDebt)
    return newDebt

## ACCOUNTING MANAGEMENT ##
@internal
def _processReport(strategy: address) -> (uint256, uint256):
    """
    Processing a report means comparing the debt that the strategy has taken 
    with the current amount of funds it is reporting. If the strategy owes 
    less than it currently has, it means it has had a profit, else (assets < debt) 
    it has had a loss.

    Different strategies might choose different reporting strategies: pessimistic, 
    only realised P&L, ... The best way to report depends on the strategy.

    The profit will be distributed following a smooth curve over the vaults 
    profitMaxUnlockTime seconds. Losses will be taken immediately, first from the 
    profit buffer (avoiding an impact in pps), then will reduce pps.

    Any applicable fees are charged and distributed during the report as well
    to the specified recipients.
    """
    # Make sure we have a valid strategy.
    assert self.strategies[strategy].activation != 0, "inactive strategy"

    # Vault assesses profits using 4626 compliant interface. 
    # NOTE: It is important that a strategies `convertToAssets` implementation
    # cannot be manipulated or else the vault could report incorrect gains/losses.
    strategyShares: uint256 = IStrategy(strategy).balanceOf(self)
    # How much the vaults position is worth.
    totalAssets: uint256 = IStrategy(strategy).convertToAssets(strategyShares)
    # How much the vault had deposited to the strategy.
    currentDebt: uint256 = self.strategies[strategy].currentDebt

    gain: uint256 = 0
    loss: uint256 = 0

    ### Asses Gain or Loss ###

    # Compare reported assets vs. the current debt.
    if totalAssets > currentDebt:
        # We have a gain.
        gain = unsafe_sub(totalAssets, currentDebt)
    else:
        # We have a loss.
        loss = unsafe_sub(currentDebt, totalAssets)
    
    # Cache `asset` for repeated use.
    _asset: address = self.asset

    ### Asses Fees and Refunds ###

    # For Accountant fee assessment.
    totalFees: uint256 = 0
    totalRefunds: uint256 = 0
    # If accountant is not set, fees and refunds remain unchanged.
    accountant: address = self.accountant
    if accountant != empty(address):
        totalFees, totalRefunds = IAccountant(accountant).report(strategy, gain, loss)

        if totalRefunds > 0:
            # Make sure we have enough approval and enough asset to pull.
            totalRefunds = min(totalRefunds, min(ERC20(_asset).balanceOf(accountant), ERC20(_asset).allowance(accountant, self)))

    # Total fees to charge in shares.
    totalFeesShares: uint256 = 0
    # For Protocol fee assessment.
    protocolFeeBps: uint16 = 0
    protocolFeesShares: uint256 = 0
    protocolFeeRecipient: address = empty(address)
    # `sharesToBurn` is derived from amounts that would reduce the vaults PPS.
    # NOTE: this needs to be done before any pps changes
    sharesToBurn: uint256 = 0
    # Only need to burn shares if there is a loss or fees.
    if loss + totalFees > 0:
        # The amount of shares we will want to burn to offset losses and fees.
        sharesToBurn = self._convertToShares(loss + totalFees, Rounding.ROUND_UP)

        # If we have fees then get the proportional amount of shares to issue.
        if totalFees > 0:
            # Get the total amount shares to issue for the fees.
            totalFeesShares = sharesToBurn * totalFees / (loss + totalFees)

            # Get the protocol fee config for this vault.
            protocolFeeBps, protocolFeeRecipient = IFactory(self.factory).protocolFeeConfig()

            # If there is a protocol fee.
            if protocolFeeBps > 0:
                # Get the percent of fees to go to protocol fees.
                protocolFeesShares = totalFeesShares * convert(protocolFeeBps, uint256) / MAX_BPS


    # Shares to lock is any amount that would otherwise increase the vaults PPS.
    sharesToLock: uint256 = 0
    profitMaxUnlockTime: uint256 = self._profitMaxUnlockTime
    # Get the amount we will lock to avoid a PPS increase.
    if gain + totalRefunds > 0 and profitMaxUnlockTime != 0:
        sharesToLock = self._convertToShares(gain + totalRefunds, Rounding.ROUND_DOWN)

    # The total current supply including locked shares.
    totalSupply: uint256 = self._totalSupply
    # The total shares the vault currently owns. Both locked and unlocked.
    totalLockedShares: uint256 = self._balanceOf[self]
    # Get the desired end amount of shares after all accounting.
    endingSupply: uint256 = totalSupply + sharesToLock - sharesToBurn - self._unlockedShares()
    
    # If we will end with more shares than we have now.
    if endingSupply > totalSupply:
        # Issue the difference.
        self._issueShares(unsafe_sub(endingSupply, totalSupply), self)

    # Else we need to burn shares.
    elif totalSupply > endingSupply:
        # Can't burn more than the vault owns.
        toBurn: uint256 = min(unsafe_sub(totalSupply, endingSupply), totalLockedShares)
        self._burnShares(toBurn, self)

    # Adjust the amount to lock for this period.
    if sharesToLock > sharesToBurn:
        # Don't lock fees or losses.
        sharesToLock = unsafe_sub(sharesToLock, sharesToBurn)
    else:
        sharesToLock = 0

    # Pull refunds
    if totalRefunds > 0:
        # Transfer the refunded amount of asset to the vault.
        self._erc20SafeTransferFrom(_asset, accountant, self, totalRefunds)
        # Update storage to increase total assets.
        self._totalIdle += totalRefunds

    # Record any reported gains.
    if gain > 0:
        # NOTE: this will increase totalAssets
        currentDebt = unsafe_add(currentDebt, gain)
        self.strategies[strategy].currentDebt = currentDebt
        self._totalDebt += gain

    # Or record any reported loss
    elif loss > 0:
        currentDebt = unsafe_sub(currentDebt, loss)
        self.strategies[strategy].currentDebt = currentDebt
        self._totalDebt -= loss

    # Issue shares for fees that were calculated above if applicable.
    if totalFeesShares > 0:
        # Accountant fees are (totalFees - protocolFees).
        self._issueShares(totalFeesShares - protocolFeesShares, accountant)

        # If we also have protocol fees.
        if protocolFeesShares > 0:
            self._issueShares(protocolFeesShares, protocolFeeRecipient)

    # Update unlocking rate and time to fully unlocked.
    totalLockedShares = self._balanceOf[self]
    if totalLockedShares > 0:
        previouslyLockedTime: uint256 = 0
        _fullProfitUnlockDate: uint256 = self._fullProfitUnlockDate
        # Check if we need to account for shares still unlocking.
        if _fullProfitUnlockDate > block.timestamp: 
            # There will only be previously locked shares if time remains.
            # We calculate this here since it will not occur every time we lock shares.
            previouslyLockedTime = (totalLockedShares - sharesToLock) * (_fullProfitUnlockDate - block.timestamp)

        # newProfitLockingPeriod is a weighted average between the remaining time of the previously locked shares and the profitMaxUnlockTime
        newProfitLockingPeriod: uint256 = (previouslyLockedTime + sharesToLock * profitMaxUnlockTime) / totalLockedShares
        # Calculate how many shares unlock per second.
        self._profitUnlockingRate = totalLockedShares * MAX_BPS_EXTENDED / newProfitLockingPeriod
        # Calculate how long until the full amount of shares is unlocked.
        self._fullProfitUnlockDate = block.timestamp + newProfitLockingPeriod
        # Update the last profitable report timestamp.
        self._lastProfitUpdate = block.timestamp
    else:
        # NOTE: only setting this to the 0 will turn in the desired effect, 
        # no need to update profitUnlockingRate
        self._fullProfitUnlockDate = 0
    
    # Record the report of profit timestamp.
    self.strategies[strategy].lastReport = block.timestamp

    # We have to recalculate the fees paid for cases with an overall loss or no profit locking
    if loss + totalFees > gain + totalRefunds or profitMaxUnlockTime == 0:
        totalFees = self._convertToAssets(totalFeesShares, Rounding.ROUND_DOWN)

    log StrategyReported(
        strategy,
        gain,
        loss,
        currentDebt,
        totalFees * convert(protocolFeeBps, uint256) / MAX_BPS, # Protocol Fees
        totalFees,
        totalRefunds
    )

    return (gain, loss)

# SETTERS #
@external
def setAccountant(newAccountant: address):
    """
    @notice Set the new accountant address.
    @param newAccountant The new accountant address.
    """
    self._enforceRole(msg.sender, Roles.ACCOUNTANT_MANAGER)
    self.accountant = newAccountant

    log UpdateAccountant(newAccountant)

@external
def setDefaultQueue(newDefaultQueue: DynArray[address, MAX_QUEUE]):
    """
    @notice Set the new default queue array.
    @dev Will check each strategy to make sure it is active. But will not
        check that the same strategy is not added twice. maxRedeem and maxWithdraw
        return values may be inaccurate if a strategy is added twice.
    @param newDefaultQueue The new default queue array.
    """
    self._enforceRole(msg.sender, Roles.QUEUE_MANAGER)

    # Make sure every strategy in the new queue is active.
    for strategy in newDefaultQueue:
        assert self.strategies[strategy].activation != 0, "!inactive"

    # Save the new queue.
    self.defaultQueue = newDefaultQueue

    log UpdateDefaultQueue(newDefaultQueue)

@external
def setUseDefaultQueue(useDefaultQueue: bool):
    """
    @notice Set a new value for `useDefaultQueue`.
    @dev If set `True` the default queue will always be
        used no matter whats passed in.
    @param useDefaultQueue new value.
    """
    self._enforceRole(msg.sender, Roles.QUEUE_MANAGER)
    self.useDefaultQueue = useDefaultQueue

    log UpdateUseDefaultQueue(useDefaultQueue)

@external
def setDepositLimit(depositLimit: uint256, override: bool = False):
    """
    @notice Set the new deposit limit.
    @dev Can not be changed if a depositLimitModule
    is set unless the override flag is true or if shutdown.
    @param depositLimit The new deposit limit.
    @param override If a `depositLimitModule` already set should be overridden.
    """
    assert self.shutdown == False # Dev: shutdown
    self._enforceRole(msg.sender, Roles.DEPOSIT_LIMIT_MANAGER)

    # If we are overriding the deposit limit module.
    if override:
        # Make sure it is set to address 0 if not already.
        if self.depositLimitModule != empty(address):

            self.depositLimitModule = empty(address)
            log UpdateDepositLimitModule(empty(address))
    else:  
        # Make sure the depositLimitModule has been set to address(0).
        assert self.depositLimitModule == empty(address), "using module"

    self.depositLimit = depositLimit

    log UpdateDepositLimit(depositLimit)

@external
def setDepositLimitModule(depositLimitModule: address, override: bool = False):
    """
    @notice Set a contract to handle the deposit limit.
    @dev The default `depositLimit` will need to be set to
    max uint256 since the module will override it or the override flag
    must be set to true to set it to max in 1 tx..
    @param depositLimitModule Address of the module.
    @param override If a `depositLimit` already set should be overridden.
    """
    assert self.shutdown == False # Dev: shutdown
    self._enforceRole(msg.sender, Roles.DEPOSIT_LIMIT_MANAGER)

    # If we are overriding the deposit limit
    if override:
        # Make sure it is max uint256 if not already.
        if self.depositLimit != max_value(uint256):

            self.depositLimit = max_value(uint256)
            log UpdateDepositLimit(max_value(uint256))
    else:
        # Make sure the depositLimit has been set to uint max.
        assert self.depositLimit == max_value(uint256), "using deposit limit"

    self.depositLimitModule = depositLimitModule

    log UpdateDepositLimitModule(depositLimitModule)

@external
def setWithdrawLimitModule(withdrawLimitModule: address):
    """
    @notice Set a contract to handle the withdraw limit.
    @dev This will override the default `maxWithdraw`.
    @param withdrawLimitModule Address of the module.
    """
    self._enforceRole(msg.sender, Roles.WITHDRAW_LIMIT_MANAGER)

    self.withdrawLimitModule = withdrawLimitModule

    log UpdateWithdrawLimitModule(withdrawLimitModule)

@external
def setMinimumTotalIdle(minimumTotalIdle: uint256):
    """
    @notice Set the new minimum total idle.
    @param minimumTotalIdle The new minimum total idle.
    """
    self._enforceRole(msg.sender, Roles.MINIMUM_IDLE_MANAGER)
    self.minimumTotalIdle = minimumTotalIdle

    log UpdateMinimumTotalIdle(minimumTotalIdle)

@external
def setProfitMaxUnlockTime(newProfitMaxUnlockTime: uint256):
    """
    @notice Set the new profit max unlock time.
    @dev The time is denominated in seconds and must be less than 1 year.
        We only need to update locking period if setting to 0,
        since the current period will use the old rate and on the next
        report it will be reset with the new unlocking time.
    
        Setting to 0 will cause any currently locked profit to instantly
        unlock and an immediate increase in the vaults Price Per Share.

    @param newProfitMaxUnlockTime The new profit max unlock time.
    """
    self._enforceRole(msg.sender, Roles.PROFIT_UNLOCK_MANAGER)
    # Must be less than one year for report cycles
    assert newProfitMaxUnlockTime <= 31_556_952, "profit unlock time too long"

    # If setting to 0 we need to reset any locked values.
    if (newProfitMaxUnlockTime == 0):

        shareBalance: uint256 = self._balanceOf[self]
        if shareBalance > 0:
            # Burn any shares the vault still has.
            self._burnShares(shareBalance, self)

        # Reset unlocking variables to 0.
        self._profitUnlockingRate = 0
        self._fullProfitUnlockDate = 0

    self._profitMaxUnlockTime = newProfitMaxUnlockTime

    log UpdateProfitMaxUnlockTime(newProfitMaxUnlockTime)

# ROLE MANAGEMENT #
@internal
def _enforceRole(account: address, role: Roles):
    # Make sure the sender holds the role.
    assert role in self.roles[account], "not allowed"

@external
def setRole(account: address, role: Roles):
    """
    @notice Set the roles for an account.
    @dev This will fully override an accounts current roles
     so it should include all roles the account should hold.
    @param account The account to set the role for.
    @param role The roles the account should hold.
    """
    assert msg.sender == self.roleManager
    self.roles[account] = role

    log RoleSet(account, role)

@external
def addRole(account: address, role: Roles):
    """
    @notice Add a new role to an address.
    @dev This will add a new role to the account
     without effecting any of the previously held roles.
    @param account The account to add a role to.
    @param role The new role to add to account.
    """
    assert msg.sender == self.roleManager
    self.roles[account] = self.roles[account] | role

    log RoleSet(account, self.roles[account])

@external
def removeRole(account: address, role: Roles):
    """
    @notice Remove a single role from an account.
    @dev This will leave all other roles for the 
     account unchanged.
    @param account The account to remove a Role from.
    @param role The Role to remove.
    """
    assert msg.sender == self.roleManager
    self.roles[account] = self.roles[account] & ~role

    log RoleSet(account, self.roles[account])
    
@external
def transferRoleManager(roleManager: address):
    """
    @notice Step 1 of 2 in order to transfer the 
        role manager to a new address. This will set
        the futureRoleManager. Which will then need
        to be accepted by the new manager.
    @param roleManager The new role manager address.
    """
    assert msg.sender == self.roleManager
    self.futureRoleManager = roleManager

@external
def acceptRoleManager():
    """
    @notice Accept the role manager transfer.
    """
    assert msg.sender == self.futureRoleManager
    self.roleManager = msg.sender
    self.futureRoleManager = empty(address)

    log UpdateRoleManager(msg.sender)

# VAULT STATUS VIEWS

@view
@external
def isShutdown() -> bool:
    """
    @notice Get if the vault is shutdown.
    @return Bool representing the shutdown status
    """
    return self.shutdown
@view
@external
def unlockedShares() -> uint256:
    """
    @notice Get the amount of shares that have been unlocked.
    @return The amount of shares that are have been unlocked.
    """
    return self._unlockedShares()

@view
@external
def pricePerShare() -> uint256:
    """
    @notice Get the price per share (pps) of the vault.
    @dev This value offers limited precision. Integrations that require 
        exact precision should use convertToAssets or convertToShares instead.
    @return The price per share.
    """
    return self._convertToAssets(10 ** convert(self.decimals, uint256), Rounding.ROUND_DOWN)

@view
@external
def getDefaultQueue() -> DynArray[address, MAX_QUEUE]:
    """
    @notice Get the full default queue currently set.
    @return The current default withdrawal queue.
    """
    return self.defaultQueue

## REPORTING MANAGEMENT ##
@external
@nonreentrant("lock")
def processReport(strategy: address) -> (uint256, uint256):
    """
    @notice Process the report of a strategy.
    @param strategy The strategy to process the report for.
    @return The gain and loss of the strategy.
    """
    self._enforceRole(msg.sender, Roles.REPORTING_MANAGER)
    return self._processReport(strategy)

@external
@nonreentrant("lock")
def buyDebt(strategy: address, amount: uint256):
    """
    @notice Used for governance to buy bad debt from the vault.
    @dev This should only ever be used in an emergency in place
    of force revoking a strategy in order to not report a loss.
    It allows the DEBT_PURCHASER role to buy the strategies debt
    for an equal amount of `asset`. 

    @param strategy The strategy to buy the debt for
    @param amount The amount of debt to buy from the vault.
    """
    self._enforceRole(msg.sender, Roles.DEBT_PURCHASER)
    assert self.strategies[strategy].activation != 0, "not active"
    
    # Cache the current debt.
    currentDebt: uint256 = self.strategies[strategy].currentDebt
    _amount: uint256 = amount

    assert currentDebt > 0, "nothing to buy"
    assert _amount > 0, "nothing to buy with"
    
    if _amount > currentDebt:
        _amount = currentDebt

    # We get the proportion of the debt that is being bought and
    # transfer the equivalent shares. We assume this is being used
    # due to strategy issues so won't rely on its conversion rates.
    shares: uint256 = IStrategy(strategy).balanceOf(self) * _amount / currentDebt

    assert shares > 0, "cannot buy zero"

    self._erc20SafeTransferFrom(self.asset, msg.sender, self, _amount)

    # Lower strategy debt
    self.strategies[strategy].currentDebt -= _amount
    # lower total debt
    self._totalDebt -= _amount
    # Increase total idle
    self._totalIdle += _amount

    # log debt change
    log DebtUpdated(strategy, currentDebt, currentDebt - _amount)

    # Transfer the strategies shares out.
    self._erc20SafeTransfer(strategy, msg.sender, shares)

    log DebtPurchased(strategy, _amount)

## STRATEGY MANAGEMENT ##
@external
def addStrategy(newStrategy: address, addToQueue: bool=True):
    """
    @notice Add a new strategy.
    @param newStrategy The new strategy to add.
    """
    self._enforceRole(msg.sender, Roles.ADD_STRATEGY_MANAGER)
    self._addStrategy(newStrategy, addToQueue)

@external
def revokeStrategy(strategy: address):
    """
    @notice Revoke a strategy.
    @param strategy The strategy to revoke.
    """
    self._enforceRole(msg.sender, Roles.REVOKE_STRATEGY_MANAGER)
    self._revokeStrategy(strategy)

@external
def forceRevokeStrategy(strategy: address):
    """
    @notice Force revoke a strategy.
    @dev The vault will remove the strategy and write off any debt left 
        in it as a loss. This function is a dangerous function as it can force a 
        strategy to take a loss. All possible assets should be removed from the 
        strategy first via updateDebt. If a strategy is removed erroneously it 
        can be re-added and the loss will be credited as profit. Fees will apply.
    @param strategy The strategy to force revoke.
    """
    self._enforceRole(msg.sender, Roles.FORCE_REVOKE_MANAGER)
    self._revokeStrategy(strategy, True)

## DEBT MANAGEMENT ##
@external
def updateMaxDebtForStrategy(strategy: address, newMaxDebt: uint256):
    """
    @notice Update the max debt for a strategy.
    @param strategy The strategy to update the max debt for.
    @param newMaxDebt The new max debt for the strategy.
    """
    self._enforceRole(msg.sender, Roles.MAX_DEBT_MANAGER)
    assert self.strategies[strategy].activation != 0, "inactive strategy"
    self.strategies[strategy].maxDebt = newMaxDebt

    log UpdatedMaxDebtForStrategy(msg.sender, strategy, newMaxDebt)

@external
@nonreentrant("lock")
def updateDebt(
    strategy: address, 
    targetDebt: uint256, 
    maxLoss: uint256 = MAX_BPS
) -> uint256:
    """
    @notice Update the debt for a strategy.
    @param strategy The strategy to update the debt for.
    @param targetDebt The target debt for the strategy.
    @param maxLoss Optional to check realized losses on debt decreases.
    @return The amount of debt added or removed.
    """
    self._enforceRole(msg.sender, Roles.DEBT_MANAGER)
    return self._updateDebt(strategy, targetDebt, maxLoss)

## EMERGENCY MANAGEMENT ##
@external
def shutdownVault():
    """
    @notice Shutdown the vault.
    """
    self._enforceRole(msg.sender, Roles.EMERGENCY_MANAGER)
    assert self.shutdown == False
    
    # Shutdown the vault.
    self.shutdown = True

    # Set deposit limit to 0.
    if self.depositLimitModule != empty(address):
        self.depositLimitModule = empty(address)

        log UpdateDepositLimitModule(empty(address))

    self.depositLimit = 0
    log UpdateDepositLimit(0)

    self.roles[msg.sender] = self.roles[msg.sender] | Roles.DEBT_MANAGER
    log Shutdown()


## SHARE MANAGEMENT ##
## ERC20 + ERC4626 ##
@external
@nonreentrant("lock")
def deposit(assets: uint256, receiver: address) -> uint256:
    """
    @notice Deposit assets into the vault.
    @param assets The amount of assets to deposit.
    @param receiver The address to receive the shares.
    @return The amount of shares minted.
    """
    return self._deposit(msg.sender, receiver, assets)

@external
@nonreentrant("lock")
def mint(shares: uint256, receiver: address) -> uint256:
    """
    @notice Mint shares for the receiver.
    @param shares The amount of shares to mint.
    @param receiver The address to receive the shares.
    @return The amount of assets deposited.
    """
    return self._mint(msg.sender, receiver, shares)

@external
@nonreentrant("lock")
def withdraw(
    assets: uint256, 
    receiver: address, 
    owner: address, 
    maxLoss: uint256 = 0,
    strategies: DynArray[address, MAX_QUEUE] = []
) -> uint256:
    """
    @notice Withdraw an amount of asset to `receiver` burning `owner`s shares.
    @dev The default behavior is to not allow any loss.
    @param assets The amount of asset to withdraw.
    @param receiver The address to receive the assets.
    @param owner The address who's shares are being burnt.
    @param maxLoss Optional amount of acceptable loss in Basis Points.
    @param strategies Optional array of strategies to withdraw from.
    @return The amount of shares actually burnt.
    """
    shares: uint256 = self._convertToShares(assets, Rounding.ROUND_UP)
    self._redeem(msg.sender, receiver, owner, assets, shares, maxLoss, strategies)
    return shares

@external
@nonreentrant("lock")
def redeem(
    shares: uint256, 
    receiver: address, 
    owner: address, 
    maxLoss: uint256 = MAX_BPS,
    strategies: DynArray[address, MAX_QUEUE] = []
) -> uint256:
    """
    @notice Redeems an amount of shares of `owners` shares sending funds to `receiver`.
    @dev The default behavior is to allow losses to be realized.
    @param shares The amount of shares to burn.
    @param receiver The address to receive the assets.
    @param owner The address who's shares are being burnt.
    @param maxLoss Optional amount of acceptable loss in Basis Points.
    @param strategies Optional array of strategies to withdraw from.
    @return The amount of assets actually withdrawn.
    """
    assets: uint256 = self._convertToAssets(shares, Rounding.ROUND_DOWN)
    # Always return the actual amount of assets withdrawn.
    return self._redeem(msg.sender, receiver, owner, assets, shares, maxLoss, strategies)


@external
def approve(spender: address, amount: uint256) -> bool:
    """
    @notice Approve an address to spend the vault's shares.
    @param spender The address to approve.
    @param amount The amount of shares to approve.
    @return True if the approval was successful.
    """
    return self._approve(msg.sender, spender, amount)

@external
def transfer(receiver: address, amount: uint256) -> bool:
    """
    @notice Transfer shares to a receiver.
    @param receiver The address to transfer shares to.
    @param amount The amount of shares to transfer.
    @return True if the transfer was successful.
    """
    assert receiver not in [self, empty(address)]
    self._transfer(msg.sender, receiver, amount)
    return True

@external
def transferFrom(sender: address, receiver: address, amount: uint256) -> bool:
    """
    @notice Transfer shares from a sender to a receiver.
    @param sender The address to transfer shares from.
    @param receiver The address to transfer shares to.
    @param amount The amount of shares to transfer.
    @return True if the transfer was successful.
    """
    assert receiver not in [self, empty(address)]
    return self._transferFrom(sender, receiver, amount)

## ERC20+4626 compatibility
@external
def permit(
    owner: address, 
    spender: address, 
    amount: uint256, 
    deadline: uint256, 
    v: uint8, 
    r: bytes32, 
    s: bytes32
) -> bool:
    """
    @notice Approve an address to spend the vault's shares.
    @param owner The address to approve.
    @param spender The address to approve.
    @param amount The amount of shares to approve.
    @param deadline The deadline for the permit.
    @param v The v component of the signature.
    @param r The r component of the signature.
    @param s The s component of the signature.
    @return True if the approval was successful.
    """
    return self._permit(owner, spender, amount, deadline, v, r, s)

@view
@external
def balanceOf(addr: address) -> uint256:
    """
    @notice Get the balance of a user.
    @param addr The address to get the balance of.
    @return The balance of the user.
    """
    if(addr == self):
        # If the address is the vault, account for locked shares.
        return self._balanceOf[addr] - self._unlockedShares()

    return self._balanceOf[addr]

@view
@external
def totalSupply() -> uint256:
    """
    @notice Get the total supply of shares.
    @return The total supply of shares.
    """
    return self._totalLockedSupply()

@view
@external
def totalAssets() -> uint256:
    """
    @notice Get the total assets held by the vault.
    @return The total assets held by the vault.
    """
    return self._totalAssets()

@view
@external
def totalIdle() -> uint256:
    """
    @notice Get the amount of loose `asset` the vault holds.
    @return The current total idle.
    """
    return self._totalIdle

@view
@external
def totalDebt() -> uint256:
    """
    @notice Get the the total amount of funds invested
    across all strategies.
    @return The current total debt.
    """
    return self._totalDebt

@view
@external
def convertToShares(assets: uint256) -> uint256:
    """
    @notice Convert an amount of assets to shares.
    @param assets The amount of assets to convert.
    @return The amount of shares.
    """
    return self._convertToShares(assets, Rounding.ROUND_DOWN)

@view
@external
def previewDeposit(assets: uint256) -> uint256:
    """
    @notice Preview the amount of shares that would be minted for a deposit.
    @param assets The amount of assets to deposit.
    @return The amount of shares that would be minted.
    """
    return self._convertToShares(assets, Rounding.ROUND_DOWN)

@view
@external
def previewMint(shares: uint256) -> uint256:
    """
    @notice Preview the amount of assets that would be deposited for a mint.
    @param shares The amount of shares to mint.
    @return The amount of assets that would be deposited.
    """
    return self._convertToAssets(shares, Rounding.ROUND_UP)

@view
@external
def convertToAssets(shares: uint256) -> uint256:
    """
    @notice Convert an amount of shares to assets.
    @param shares The amount of shares to convert.
    @return The amount of assets.
    """
    return self._convertToAssets(shares, Rounding.ROUND_DOWN)

@view
@external
def maxDeposit(receiver: address) -> uint256:
    """
    @notice Get the maximum amount of assets that can be deposited.
    @param receiver The address that will receive the shares.
    @return The maximum amount of assets that can be deposited.
    """
    return self._maxDeposit(receiver)

@view
@external
def maxMint(receiver: address) -> uint256:
    """
    @notice Get the maximum amount of shares that can be minted.
    @param receiver The address that will receive the shares.
    @return The maximum amount of shares that can be minted.
    """
    maxDeposit: uint256 = self._maxDeposit(receiver)
    return self._convertToShares(maxDeposit, Rounding.ROUND_DOWN)

@view
@external
def maxWithdraw(
    owner: address,
    maxLoss: uint256 = 0,
    strategies: DynArray[address, MAX_QUEUE] = []
) -> uint256:
    """
    @notice Get the maximum amount of assets that can be withdrawn.
    @dev Complies to normal 4626 interface and takes custom params.
    NOTE: Passing in a incorrectly ordered queue may result in
     incorrect returns values.
    @param owner The address that owns the shares.
    @param maxLoss Custom maxLoss if any.
    @param strategies Custom strategies queue if any.
    @return The maximum amount of assets that can be withdrawn.
    """
    return self._maxWithdraw(owner, maxLoss, strategies)

@view
@external
def maxRedeem(
    owner: address,
    maxLoss: uint256 = MAX_BPS,
    strategies: DynArray[address, MAX_QUEUE] = []
) -> uint256:
    """
    @notice Get the maximum amount of shares that can be redeemed.
    @dev Complies to normal 4626 interface and takes custom params.
    NOTE: Passing in a incorrectly ordered queue may result in
     incorrect returns values.
    @param owner The address that owns the shares.
    @param maxLoss Custom maxLoss if any.
    @param strategies Custom strategies queue if any.
    @return The maximum amount of shares that can be redeemed.
    """
    return min(
        # Min of the shares equivalent of maxWithdraw or the full balance
        self._convertToShares(self._maxWithdraw(owner, maxLoss, strategies), Rounding.ROUND_DOWN),
        self._balanceOf[owner]
    )

@view
@external
def previewWithdraw(assets: uint256) -> uint256:
    """
    @notice Preview the amount of shares that would be redeemed for a withdraw.
    @param assets The amount of assets to withdraw.
    @return The amount of shares that would be redeemed.
    """
    return self._convertToShares(assets, Rounding.ROUND_UP)

@view
@external
def previewRedeem(shares: uint256) -> uint256:
    """
    @notice Preview the amount of assets that would be withdrawn for a redeem.
    @param shares The amount of shares to redeem.
    @return The amount of assets that would be withdrawn.
    """
    return self._convertToAssets(shares, Rounding.ROUND_DOWN)

@view
@external
def FACTORY() -> address:
    """
    @notice Address of the factory that deployed the vault.
    @dev Is used to retrieve the protocol fees.
    @return Address of the vault factory.
    """
    return self.factory

@view
@external
def apiVersion() -> String[28]:
    """
    @notice Get the API version of the vault.
    @return The API version of the vault.
    """
    return API_VERSION

@view
@external
def assessShareOfUnrealisedLosses(strategy: address, assetsNeeded: uint256) -> uint256:
    """
    @notice Assess the share of unrealised losses that a strategy has.
    @param strategy The address of the strategy.
    @param assetsNeeded The amount of assets needed to be withdrawn.
    @return The share of unrealised losses that the strategy has.
    """
    assert self.strategies[strategy].currentDebt >= assetsNeeded

    return self._assessShareOfUnrealisedLosses(strategy, assetsNeeded)

## Profit locking getter functions ##

@view
@external
def profitMaxUnlockTime() -> uint256:
    """
    @notice Gets the current time profits are set to unlock over.
    @return The current profit max unlock time.
    """
    return self._profitMaxUnlockTime

@view
@external
def fullProfitUnlockDate() -> uint256:
    """
    @notice Gets the timestamp at which all profits will be unlocked.
    @return The full profit unlocking timestamp
    """
    return self._fullProfitUnlockDate

@view
@external
def profitUnlockingRate() -> uint256:
    """
    @notice The per second rate at which profits are unlocking.
    @dev This is denominated in EXTENDED_BPS decimals.
    @return The current profit unlocking rate.
    """
    return self._profitUnlockingRate


@view
@external
def lastProfitUpdate() -> uint256:
    """
    @notice The timestamp of the last time shares were locked.
    @return The last profit update.
    """
    return self._lastProfitUpdate

# eip-1344
@view
@internal
def domainSeparator() -> bytes32:
    return keccak256(
        concat(
            DOMAIN_TYPE_HASH,
            keccak256(convert("Gefion Vault", Bytes[12])),
            keccak256(convert(API_VERSION, Bytes[28])),
            convert(chain.id, bytes32),
            convert(self, bytes32)
        )
    )

@view
@external
def DOMAIN_SEPARATOR() -> bytes32:
    """
    @notice Get the domain separator.
    @return The domain separator.
    """
    return self.domainSeparator()
