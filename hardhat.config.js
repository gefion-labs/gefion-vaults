// See https://hardhat.org/config/ for config options.
module.exports = {
  networks: {
    hardhat: {
      chainId: 31337,
      forking: {
        // Using Alchemy
        url: `https://eth-mainnet.alchemyapi.io/v2/${ALCHEMY_KEY}`, // url to RPC node, ${ALCHEMY_KEY} - must be your API key
        // Using Infura
        // url: `https://mainnet.infura.io/v3/${INFURA_KEY}`, // ${INFURA_KEY} - must be your API key
        blockNumber: 12821000, // a specific block number with which you want to work
      },
    },
  },
};
