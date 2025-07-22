from trezorcrypto import monero as tcry

from xmr.networks import NetworkTypes, net_version

if False:
    from apps.monero.xmr.types import Ge25519
    from trezor.messages import MoneroAccountPublicAddress
    from trezor.messages import MoneroTransactionDestinationEntry

class AddressTypes:
    PRIMARY = 0
    INTEGRATED = 1
    SUB = 2

def addr_to_hash(addr: MoneroAccountPublicAddress) -> bytes:
    """
    Creates hashable address representation
    """
    return bytes(addr.spend_public_key + addr.view_public_key)


def encode_addr(
    version, spend_pub: Ge25519, view_pub: Ge25519, payment_id: bytes | None = None
) -> str:
    """
    Builds Monero address from public keys
    """
    buf = spend_pub + view_pub
    if payment_id:
        buf += bytes(payment_id)
    return tcry.xmr_base58_addr_encode_check(ord(version), bytes(buf))


def decode_addr(addr: bytes) -> tuple[int, bytes, bytes]:
    """
    Given address, get version and public spend and view keys.
    """
    d, version = tcry.xmr_base58_addr_decode_check(bytes(addr))
    pub_spend_key = d[0:32]
    pub_view_key = d[32:64]
    return version, pub_spend_key, pub_view_key


def public_addr_encode(
    pub_addr: MoneroAccountPublicAddress, is_sub=False, net=NetworkTypes.MAINNET
):
    """
    Encodes public address to Monero address
    """
    net_ver = net_version(net, is_sub)
    return encode_addr(net_ver, pub_addr.spend_public_key, pub_addr.view_public_key)


def classify_subaddresses(
    tx_dests: list[MoneroTransactionDestinationEntry],
    change_addr: MoneroAccountPublicAddress,
) -> tuple[int, int, int]:
    """
    Classify destination subaddresses
    """
    num_stdaddresses = 0
    num_subaddresses = 0
    single_dest_subaddress = None
    addr_set = set()
    for tx in tx_dests:
        if change_addr and addr_eq(change_addr, tx.addr):
            continue
        addr_hashed = addr_to_hash(tx.addr)
        if addr_hashed in addr_set:
            continue
        addr_set.add(addr_hashed)
        if tx.is_subaddress:
            num_subaddresses += 1
            single_dest_subaddress = tx.addr
        else:
            num_stdaddresses += 1
    return num_stdaddresses, num_subaddresses, single_dest_subaddress


def addr_eq(a: MoneroAccountPublicAddress, b: MoneroAccountPublicAddress):
    return (
        a.spend_public_key == b.spend_public_key
        and a.view_public_key == b.view_public_key
    )


def get_change_addr_idx(
    outputs: list[MoneroTransactionDestinationEntry],
    change_dts: MoneroTransactionDestinationEntry,
) -> int:
    """
    Returns ID of the change output from the change_dts and outputs
    """
    if change_dts is None:
        return None

    change_idx = None
    for idx, dst in enumerate(outputs):
        if (
            change_dts.amount
            and change_dts.amount == dst.amount
            and addr_eq(change_dts.addr, dst.addr)
        ):
            change_idx = idx
    return change_idx

def is_valid_address(address):
    from xmr.addresses import decode_addr
    prefix = 'monero:'
    if address[0:len(prefix)].lower() == prefix:
        params_start = address.find('?')
        if params_start == -1:
            params_start = len(address)

        address = address[len(prefix):params_start]

    try:
        version, _, _ = decode_addr(bytes(address, 'ascii'))
    except Exception as e:
        return '', False, -1

    return address, True, version

def get_address_info(address=None, network_prefix=None):
    from xmr.networks import MainNet, TestNet, StageNet
    if network_prefix == None:
        if address == None:
            return None, None, None
        address, is_valid, network_prefix = is_valid_address(address)
        if not is_valid:
            return None, None, None

    network_type = None
    address_type = None
    if network_prefix == MainNet.PUBLIC_ADDRESS_BASE58_PREFIX:
        network_type = NetworkTypes.MAINNET
        address_type = AddressTypes.PRIMARY
    elif network_prefix == MainNet.PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX:
        network_type = NetworkTypes.MAINNET
        address_type = AddressTypes.INTEGRATED
    elif network_prefix == MainNet.PUBLIC_SUBADDRESS_BASE58_PREFIX:
        network_type = NetworkTypes.MAINNET
        address_type = AddressTypes.SUB
    elif network_prefix == TestNet.PUBLIC_ADDRESS_BASE58_PREFIX:
        network_type = NetworkTypes.TESTNET
        address_type = AddressTypes.PRIMARY
    elif network_prefix == TestNet.PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX:
        network_type = NetworkTypes.TESTNET
        address_type = AddressTypes.INTEGRATED
    elif network_prefix == TestNet.PUBLIC_SUBADDRESS_BASE58_PREFIX:
        network_type = NetworkTypes.TESTNET
        address_type = AddressTypes.SUB
    elif network_prefix == StageNet.PUBLIC_ADDRESS_BASE58_PREFIX:
        network_type = NetworkTypes.STAGENET
        address_type = AddressTypes.PRIMARY
    elif network_prefix == StageNet.PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX:
        network_type = NetworkTypes.STAGENET
        address_type = AddressTypes.INTEGRATED
    elif network_prefix == StageNet.PUBLIC_SUBADDRESS_BASE58_PREFIX:
        network_type = NetworkTypes.STAGENET
        address_type = AddressTypes.SUB

    return address, network_type, address_type
