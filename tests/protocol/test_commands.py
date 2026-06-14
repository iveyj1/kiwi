from kiwi_client.commands import (
    AgcSettings,
    encode_agc,
    encode_auth,
    encode_basic_snd_setup,
    encode_compression,
    encode_ident_user,
    encode_keepalive,
    encode_modulation,
)


def test_encode_auth_without_password():
    assert encode_auth() == "SET auth t=kiwi p="


def test_encode_auth_with_tlimit_password_uses_hash_placeholder():
    assert encode_auth(tlimit_password="limit") == "SET auth t=kiwi p=# ipl=limit"


def test_encode_identity_mode_agc_compression_keepalive():
    assert encode_ident_user("kiwi-client") == "SET ident_user=kiwi-client"
    assert encode_modulation("AM", -4900, 4900, 4625.0) == "SET mod=am low_cut=-4900 high_cut=4900 freq=4625.000"
    assert encode_agc() == "SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=50"
    assert encode_agc(AgcSettings(on=False, gain=42)) == "SET agc=0 hang=0 thresh=-100 slope=6 decay=1000 manGain=42"
    assert encode_compression(False) == "SET compression=0"
    assert encode_compression(True) == "SET compression=1"
    assert encode_keepalive() == "SET keepalive"


def test_encode_basic_snd_setup_sequence():
    assert encode_basic_snd_setup(user="kiwi-client", frequency_khz=4625.0) == [
        "SET ident_user=kiwi-client",
        "SET mod=am low_cut=-4900 high_cut=4900 freq=4625.000",
        "SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=50",
        "SET compression=0",
        "SET keepalive",
    ]
