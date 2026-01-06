

from py_clob_client.client import ClobClient

client = ClobClient(
    "https://clob.polymarket.com",
    key="c69f60bc007692e99018fc033fcc19ca6b6966fd72e8a841299607e63e62b493",  # 0x...
    chain_id=137,
)

creds = client.create_or_derive_api_creds()
print(creds)


# Address: 0xA2A5A26BD732124911C3314Be8896Ea5BC467bF1
# Private Key: c69f60bc007692e99018fc033fcc19ca6b6966fd72e8a841299607e63e62b493