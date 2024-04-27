// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.8.18;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

interface IVaultFactory {
    event NewVault(address indexed vaultAddress, address indexed asset);
    event UpdateProtocolFeeBps(
        uint16 oldProtocolFeeBps,
        uint16 newProtocolFeeBps
    );
    event UpdateProtocolFeeRecipient(
        address oldProtocolFeeRecipient,
        address newProtocolFeeRecipient
    );
    event UpdateCustomProtocolFee(address vault, uint16 newCustomProtocolFee);
    event RemovedCustomProtocolFee(address vault);
    event FactoryShutdown();
    event NewPendingGovernance(address newPendingGovernance);
    event UpdateGovernance(address newGovernance);

    function shutdown() external view returns (bool);

    function governance() external view returns (address);

    function pendingGovernance() external view returns (address);

    function name() external view returns (string memory);

    function defaultProtocolFeeConfig() external view returns (uint256);

    function customProtocolFee(address) external view returns (uint16);

    function useCustomProtocolFee(address) external view returns (bool);

    function deployNewVault(
        address asset,
        string memory name,
        string memory symbol,
        address roleManager,
        uint256 profitMaxUnlockTime
    ) external returns (address);

    function vaultOriginal() external view returns (address);

    function apiVersion() external view returns (string memory);

    function protocolFeeConfig()
        external
        view
        returns (uint16 feeBps, address feeRecipient);

    function protocolFeeConfig(
        address vault
    ) external view returns (uint16 feeBps, address feeRecipient);

    function setProtocolFeeBps(uint16 newProtocolFeeBps) external;

    function setProtocolFeeRecipient(address newProtocolFeeRecipient) external;

    function setCustomProtocolFeeBps(
        address vault,
        uint16 newCustomProtocolFee
    ) external;

    function removeCustomProtocolFee(address vault) external;

    function shutdownFactory() external;

    function setGovernance(address newGovernance) external;

    function acceptGovernance() external;
}
