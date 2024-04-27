import {
  NewVault as NewVaultEvent,
  UpdateProtocolFeeBps as UpdateProtocolFeeBpsEvent,
  UpdateProtocolFeeRecipient as UpdateProtocolFeeRecipientEvent,
  UpdateCustomProtocolFee as UpdateCustomProtocolFeeEvent,
  RemovedCustomProtocolFee as RemovedCustomProtocolFeeEvent,
  FactoryShutdown as FactoryShutdownEvent,
  UpdateGovernance as UpdateGovernanceEvent,
  NewPendingGovernance as NewPendingGovernanceEvent
} from "../generated/VaultFactory/VaultFactory"
import {
  NewVault,
  UpdateProtocolFeeBps,
  UpdateProtocolFeeRecipient,
  UpdateCustomProtocolFee,
  RemovedCustomProtocolFee,
  FactoryShutdown,
  UpdateGovernance,
  NewPendingGovernance
} from "../generated/schema"

export function handleNewVault(event: NewVaultEvent): void {
  let entity = new NewVault(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.vaultAddress = event.params.vaultAddress
  entity.asset = event.params.asset

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleUpdateProtocolFeeBps(
  event: UpdateProtocolFeeBpsEvent
): void {
  let entity = new UpdateProtocolFeeBps(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.oldFeeBps = event.params.oldFeeBps
  entity.newFeeBps = event.params.newFeeBps

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleUpdateProtocolFeeRecipient(
  event: UpdateProtocolFeeRecipientEvent
): void {
  let entity = new UpdateProtocolFeeRecipient(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.oldFeeRecipient = event.params.oldFeeRecipient
  entity.newFeeRecipient = event.params.newFeeRecipient

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleUpdateCustomProtocolFee(
  event: UpdateCustomProtocolFeeEvent
): void {
  let entity = new UpdateCustomProtocolFee(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.vault = event.params.vault
  entity.newCustomProtocolFee = event.params.newCustomProtocolFee

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleRemovedCustomProtocolFee(
  event: RemovedCustomProtocolFeeEvent
): void {
  let entity = new RemovedCustomProtocolFee(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.vault = event.params.vault

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleFactoryShutdown(event: FactoryShutdownEvent): void {
  let entity = new FactoryShutdown(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleUpdateGovernance(event: UpdateGovernanceEvent): void {
  let entity = new UpdateGovernance(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.governance = event.params.governance

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}

export function handleNewPendingGovernance(
  event: NewPendingGovernanceEvent
): void {
  let entity = new NewPendingGovernance(
    event.transaction.hash.concatI32(event.logIndex.toI32())
  )
  entity.pendingGovernance = event.params.pendingGovernance

  entity.blockNumber = event.block.number
  entity.blockTimestamp = event.block.timestamp
  entity.transactionHash = event.transaction.hash

  entity.save()
}
