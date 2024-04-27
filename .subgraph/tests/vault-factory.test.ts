import {
  assert,
  describe,
  test,
  clearStore,
  beforeAll,
  afterAll
} from "matchstick-as"
import { Address } from "@graphprotocol/graph-ts"
import { NewVault } from "../generated/schema"
import { NewVault as NewVaultEvent } from "../generated/VaultFactory/VaultFactory"
import { handleNewVault } from "../src/vault-factory"
import { createNewVaultEvent } from "./vault-factory-utils"

// Tests structure (matchstick-as >=0.5.0)
// https://thegraph.com/docs/en/developer/matchstick/#tests-structure-0-5-0

describe("Describe entity assertions", () => {
  beforeAll(() => {
    let vaultAddress = Address.fromString(
      "0x0000000000000000000000000000000000000001"
    )
    let asset = Address.fromString("0x0000000000000000000000000000000000000001")
    let newNewVaultEvent = createNewVaultEvent(vaultAddress, asset)
    handleNewVault(newNewVaultEvent)
  })

  afterAll(() => {
    clearStore()
  })

  // For more test scenarios, see:
  // https://thegraph.com/docs/en/developer/matchstick/#write-a-unit-test

  test("NewVault created and stored", () => {
    assert.entityCount("NewVault", 1)

    // 0xa16081f360e3847006db660bae1c6d1b2e17ec2a is the default address used in newMockEvent() function
    assert.fieldEquals(
      "NewVault",
      "0xa16081f360e3847006db660bae1c6d1b2e17ec2a-1",
      "vaultAddress",
      "0x0000000000000000000000000000000000000001"
    )
    assert.fieldEquals(
      "NewVault",
      "0xa16081f360e3847006db660bae1c6d1b2e17ec2a-1",
      "asset",
      "0x0000000000000000000000000000000000000001"
    )

    // More assert options:
    // https://thegraph.com/docs/en/developer/matchstick/#asserts
  })
})
