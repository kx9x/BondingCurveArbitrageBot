import settings
from web3 import Web3, HTTPProvider
from web3.auto.infura import w3
import etherscan
import json
import time
import datetime
from win10toast import ToastNotifier

class Arbitrage:
    def __init__(self, bonding_curve_address, base_asset_address, swap_asset_address):
        self.bonding_curve_address = bonding_curve_address
        self.base_asset_address = base_asset_address
        self.swap_asset_address = swap_asset_address

        self.bonding_curve = w3.eth.contract(address=bonding_curve_address, abi=etherscan.getAbi(bonding_curve_address))
        self.base_asset = w3.eth.contract(address=base_asset_address, abi=etherscan.getAbi(base_asset_address))
        self.swap_asset = w3.eth.contract(address=swap_asset_address, abi=etherscan.getAbi(swap_asset_address))

        self.bonding_curve_symbol = self.bonding_curve.functions.symbol().call()
        self.base_asset_symbol = self.base_asset.functions.symbol().call()
        self.swap_asset_symbol = self.swap_asset.functions.symbol().call()

        self.base_asset_balance = self.base_asset.functions.balanceOf(settings.MY_ADDRESS).call()
        
        self.uni_router = w3.eth.contract(address=settings.UNISWAP_ROUTER_ADRESS, abi=etherscan.getAbi(settings.UNISWAP_ROUTER_ADRESS))

        self.burn_path = [self.base_asset_address, self.swap_asset_address, self.bonding_curve_address]
        self.mint_path = [self.bonding_curve_address, self.swap_asset_address, self.base_asset_address]
    
    def mint_output(self):
        mint_amount = self.bonding_curve.functions.calculateContinuousMintReturn(self.base_asset_balance).call()
        amount_out = self.uni_router.functions.getAmountsOut(mint_amount, self.mint_path).call()
        uniswap_route = "{0} {1} -> {2} {3} -> {4} {5}".format(amount_out[0] / 1e18, 
                                                    self.bonding_curve_symbol, amount_out[1] / 1e18,
                                                    self.swap_asset_symbol, amount_out[2] / 1e18,
                                                    self.base_asset_symbol)

        mint_return = amount_out[2]
        mint_route = "{0} {1} -> {2}".format(self.base_asset_balance / 1e18, self.base_asset_symbol, uniswap_route)

        return (mint_return, mint_route)


    def burn_output(self):
        amount_out = self.uni_router.functions.getAmountsOut(self.base_asset_balance, self.burn_path).call()
        uniswap_route = "{0} {1} -> {2} {3} -> {4} {5}".format(amount_out[0] / 1e18, 
                                            self.base_asset_symbol, amount_out[1] / 1e18,
                                            self.swap_asset_symbol, amount_out[2] / 1e18,
                                            self.bonding_curve_symbol)

        bonding_curve_amount_out = amount_out[2]
        burn_return = self.bonding_curve.functions.calculateContinuousBurnReturn(bonding_curve_amount_out).call()
        return (burn_return, "{0} -> {1} {2}".format(uniswap_route, burn_return / 1e18, self.base_asset_symbol))

    def is_burn_opportunity(self):
        burn_return, burn_route = self.burn_output()
        base_asset_diff = (burn_return - self.base_asset_balance) / 1e18

        if (burn_return < self.base_asset_balance):
            return (False, base_asset_diff, burn_route)
        else:
            return (True, base_asset_diff, burn_route)
    
    def is_mint_opportunity(self):
        mint_return, mint_route = self.mint_output()
        base_asset_diff = (mint_return - self.base_asset_balance) / 1e18

        if (mint_return < self.base_asset_balance):
            return (False, base_asset_diff, mint_route)
        else:
            return (True, base_asset_diff, mint_route)

    def format_result(self, strat_name, base_asset_diff, route):
        if base_asset_diff < 0:
            return "\n".join(["No arb opportunity on {0}".format(strat_name), 
                             "You would lose {0} {1} on this trade".format(base_asset_diff, self.base_asset_symbol),
                             route])
        else:
            return "\n".join(["Arb opportunity on {0}, woohoo!".format(strat_name), 
                             "You would gain {0} {1} on this trade".format(base_asset_diff, self.base_asset_symbol),
                             route])

if __name__ == '__main__':
    if not w3.isConnected():
        print("w3 is not connected... uh oh")
        exit()

    toaster = ToastNotifier()
    toaster.show_toast(settings.ARB_BOT_TOAST_NAME, "arb bot started")

    bonding_curve_addresses = [settings.EMN_CONTRACT_ADDRESS, settings.GIL_CONTRACT_ADDRESS]

    last_profit = {}
    arb_strats = {}
    for bonding_curve in bonding_curve_addresses:
        last_profit[bonding_curve] = 0
        arb_strats[bonding_curve] = Arbitrage(bonding_curve_address=bonding_curve,
                                        base_asset_address=settings.DAI_CONTRACT_ADDRESS,
                                        swap_asset_address=settings.WETH_CONTRACT_ADDRESS)


    while(True):
        print("{0}: trying to find profitable route".format(datetime.datetime.now()))
        for bonding_curve_address in bonding_curve_addresses:
            arbitrage = arb_strats[bonding_curve_address]
            if arbitrage.base_asset_balance == 0:
                print("Warning: No {0} to spend!".format(base_asset_symbol))
                last_profit[bonding_curve] = 0
            else:
                can_profit_burn, profit_burn, burn_route = arbitrage.is_burn_opportunity()
                can_profit_mint, profit_mint, mint_route = arbitrage.is_mint_opportunity()

                if (can_profit_burn):
                    res = arbitrage.format_result("burn", profit_burn, burn_route)
                    print(res)

                    if (profit_burn > last_profit[bonding_curve_address]):
                        last_profit[bonding_curve_address] = profit_burn
                        toaster.show_toast(settings.ARB_BOT_TOAST_NAME, res)

                if (can_profit_mint):
                    res = arbitrage.format_result("mint", profit_mint, mint_route)
                    print(res)
                    
                    if (profit_mint > last_profit[bonding_curve_address]):
                        last_profit[bonding_curve_address] = profit_mint
                        toaster.show_toast(settings.ARB_BOT_TOAST_NAME, res)

        seconds_to_sleep = 60
        print("{0}: sleep for {1} seconds".format(datetime.datetime.now(), seconds_to_sleep))
        time.sleep(seconds_to_sleep)
