import { newMockEvent } from "matchstick-as"
import { ethereum, Address } from "@graphprotocol/graph-ts"
import {
  NewVault,
  UpdateProtocolFeeBps,
  UpdateProtocolFeeRecipient,
  UpdateCustomProtocolFee,
  RemovedCustomProtocolFee,
  FactoryShutdown,
  UpdateGovernance,
  NewPendingGovernance
} from "../generated/VaultFactory/VaultFactory"

export function createNewVaultEvent(
  vaultAddress: Address,
  asset: Address
): NewVault {
  let newVaultEvent = changetype<NewVault>(newMockEvent())

  newVaultEvent.parameters = new Array()

  newVaultEvent.parameters.push(
    new ethereum.EventParam(
      "vaultAddress",
      ethereum.Value.fromAddress(vaultAddress)
    )
  )
  newVaultEvent.parameters.push(
    new ethereum.EventParam("asset", ethereum.Value.fromAddress(asset))
  )

  return newVaultEvent
}

export function createUpdateProtocolFeeBpsEvent(
  oldFeeBps: i32,
  newFeeBps: i32
): UpdateProtocolFeeBps {
  let updateProtocolFeeBpsEvent = changetype<UpdateProtocolFeeBps>(
    newMockEvent()
  )

  updateProtocolFeeBpsEvent.parameters = new Array()

  updateProtocolFeeBpsEvent.parameters.push(
    new ethereum.EventParam(
      "oldFeeBps",
      ethereum.Value.fromUnsignedBigInt(BigInt.fromI32(oldFeeBps))
    )
  )
  updateProtocolFeeBpsEvent.parameters.push(
    new ethereum.EventParam(
      "newFeeBps",
      ethereum.Value.fromUnsignedBigInt(BigInt.fromI32(newFeeBps))
    )
  )

  return updateProtocolFeeBpsEvent
}

export function createUpdateProtocolFeeRecipientEvent(
  oldFeeRecipient: Address,
  newFeeRecipient: Address
): UpdateProtocolFeeRecipient {
  let updateProtocolFeeRecipientEvent = changetype<UpdateProtocolFeeRecipient>(
    newMockEvent()
  )

  updateProtocolFeeRecipientEvent.parameters = new Array()

  updateProtocolFeeRecipientEvent.parameters.push(
    new ethereum.EventParam(
      "oldFeeRecipient",
      ethereum.Value.fromAddress(oldFeeRecipient)
    )
  )
  updateProtocolFeeRecipientEvent.parameters.push(
    new ethereum.EventParam(
      "newFeeRecipient",
      ethereum.Value.fromAddress(newFeeRecipient)
    )
  )

  return updateProtocolFeeRecipientEvent
}

export function createUpdateCustomProtocolFeeEvent(
  vault: Address,
  newCustomProtocolFee: i32
): UpdateCustomProtocolFee {
  let updateCustomProtocolFeeEvent = changetype<UpdateCustomProtocolFee>(
    newMockEvent()
  )

  updateCustomProtocolFeeEvent.parameters = new Array()

  updateCustomProtocolFeeEvent.parameters.push(
    new ethereum.EventParam("vault", ethereum.Value.fromAddress(vault))
  )
  updateCustomProtocolFeeEvent.parameters.push(
    new ethereum.EventParam(
      "newCustomProtocolFee",
      ethereum.Value.fromUnsignedBigInt(BigInt.fromI32(newCustomProtocolFee))
    )
  )

  return updateCustomProtocolFeeEvent
}

export function createRemovedCustomProtocolFeeEvent(
  vault: Address
): RemovedCustomProtocolFee {
  let removedCustomProtocolFeeEvent = changetype<RemovedCustomProtocolFee>(
    newMockEvent()
  )

  removedCustomProtocolFeeEvent.parameters = new Array()

  removedCustomProtocolFeeEvent.parameters.push(
    new ethereum.EventParam("vault", ethereum.Value.fromAddress(vault))
  )

  return removedCustomProtocolFeeEvent
}

export function createFactoryShutdownEvent(): FactoryShutdown {
  let factoryShutdownEvent = changetype<FactoryShutdown>(newMockEvent())

  factoryShutdownEvent.parameters = new Array()

  return factoryShutdownEvent
}

export function createUpdateGovernanceEvent(
  governance: Address
): UpdateGovernance {
  let updateGovernanceEvent = changetype<UpdateGovernance>(newMockEvent())

  updateGovernanceEvent.parameters = new Array()

  updateGovernanceEvent.parameters.push(
    new ethereum.EventParam(
      "governance",
      ethereum.Value.fromAddress(governance)
    )
  )

  return updateGovernanceEvent
}

export function createNewPendingGovernanceEvent(
  pendingGovernance: Address
): NewPendingGovernance {
  let newPendingGovernanceEvent = changetype<NewPendingGovernance>(
    newMockEvent()
  )

  newPendingGovernanceEvent.parameters = new Array()

  newPendingGovernanceEvent.parameters.push(
    new ethereum.EventParam(
      "pendingGovernance",
      ethereum.Value.fromAddress(pendingGovernance)
    )
  )

  return newPendingGovernanceEvent
}
