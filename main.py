import json
import asyncio
from web3 import Web3
from aiohttp import ClientSession

with open('config.json') as f:
    config = json.load(f)

w3 = Web3(Web3.HTTPProvider(config['RPC_URL']))

account_address = config['ACCOUNT_ADDRESS']
private_key = config['PRIVATE_KEY']

with open('ABIs/router_abi.json') as f:
    router_abi = json.load(f)
with open('ABIs/token_abi.json') as f:
    token_abi = json.load(f)
with open('ABIs/pair_abi.json') as f:
    pair_abi = json.load(f)

eth_amount = w3.to_wei(0.001, 'ether')
min_tokens = 0

deadline = w3.eth.get_block('latest').timestamp + 120
router_contract = w3.eth.contract(address=config['ROUTER_ADDRESS'], abi=router_abi)
token_contract = w3.eth.contract(address=config['TOKEN_ADDRESS'], abi=token_abi)

async def get_token_price():
    buy_path = [w3.to_checksum_address(config['WETH_ADDRESS']), config['TOKEN_ADDRESS']]
    token_price_wei = await asyncio.get_event_loop().run_in_executor(None, router_contract.functions.getAmountsOut(w3.to_wei(0.001, 'ether'), buy_path).call)
    token_price_eth = w3.from_wei(token_price_wei[1], 'ether')
    return token_price_eth

async def swap_tokens():
    swap_tx = router_contract.functions.swapExactETHForTokens(
        min_tokens,
        [w3.to_checksum_address(config['WETH_ADDRESS']), config['TOKEN_ADDRESS']],
        account_address,
        deadline
    ).build_transaction({
        'from': account_address,
        'value': eth_amount,
        'gas': 250000,
        'gasPrice': w3.to_wei('50', 'gwei'),
        'nonce': w3.eth.get_transaction_count(account_address)
    })

    signed_swap_tx = w3.eth.account.sign_transaction(swap_tx, private_key)
    swap_tx_hash = await asyncio.get_event_loop().run_in_executor(None, w3.eth.send_raw_transaction, signed_swap_tx.rawTransaction)
    swap_tx_receipt = await asyncio.get_event_loop().run_in_executor(None, w3.eth.wait_for_transaction_receipt, swap_tx_hash)

    print(f"Buy Transaction Hash: {swap_tx_hash.hex()}")
    return swap_tx_receipt

async def approve_tokens(bought_tokens):
    approve_tx = token_contract.functions.approve(config['ROUTER_ADDRESS'], bought_tokens).build_transaction({
        'from': account_address,
        'gas': 100000,
        'gasPrice': w3.to_wei('50', 'gwei'),
        'nonce': w3.eth.get_transaction_count(account_address)
    })
    signed_approve_tx = w3.eth.account.sign_transaction(approve_tx, private_key)
    approve_tx_hash = await asyncio.get_event_loop().run_in_executor(None, w3.eth.send_raw_transaction, signed_approve_tx.rawTransaction)
    approve_tx_receipt = await asyncio.get_event_loop().run_in_executor(None, w3.eth.wait_for_transaction_receipt, approve_tx_hash)

    print(f"Approve Transaction Hash: {approve_tx_hash.hex()}")
    return approve_tx_receipt

async def sell_tokens(bought_tokens):
    deadline = w3.eth.get_block('latest').timestamp + 120

    sell_path = [config['TOKEN_ADDRESS'], w3.to_checksum_address(config['WETH_ADDRESS'])]
    sell_tx = router_contract.functions.swapExactTokensForETH(
        bought_tokens,
        0,
        sell_path,
        account_address,
        deadline
    ).build_transaction({
        'from': account_address,
        'gas': 250000,
        'gasPrice': w3.to_wei('50', 'gwei'),
        'nonce': w3.eth.get_transaction_count(account_address)
    })

    signed_sell_tx = w3.eth.account.sign_transaction(sell_tx, private_key)
    sell_tx_hash = await asyncio.get_event_loop().run_in_executor(None, w3.eth.send_raw_transaction, signed_sell_tx.rawTransaction)
    sell_tx_receipt = await asyncio.get_event_loop().run_in_executor(None, w3.eth.wait_for_transaction_receipt, sell_tx_hash)

    print(f"Sell Transaction Hash: {sell_tx_hash.hex()}")
    return sell_tx_receipt

async def main():
    pair_contract = w3.eth.contract(address=config['PAIR_ADDRESS'], abi=pair_abi)

    while True:
        reserves = pair_contract.functions.getReserves().call()
        reserve0 = reserves[0]

        if reserve0 > 0:
            initial_token_price_eth = await get_token_price()
            print(f"Initial Token Price: {initial_token_price_eth} Token")

            swap_tx_receipt = await swap_tokens()
            bought_tokens = token_contract.functions.balanceOf(account_address).call()
            approve_tx_receipt = await approve_tokens(bought_tokens)

            async with ClientSession() as session:
                while True:
                    current_token_price_eth = await get_token_price()
                    print(f"Current Token Price: {current_token_price_eth} Token")

                    if current_token_price_eth <= initial_token_price_eth / 2:
                        await sell_tokens(bought_tokens)
                        print("Selling completed. Exiting...")
                        return

                    await asyncio.sleep(0.1)
        else:
            print("Token Liquidity is ZERO. Retrying...")

        await asyncio.sleep(0.1)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
