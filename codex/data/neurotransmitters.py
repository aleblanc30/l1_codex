NEURO_TRANSMITTER_NAMES = {
    "DA": "dopamine",
    "SER": "serotonin",
    "GABA": "gabaergic",
    "GLUT": "glutamate",
    "ACH": "acetylcholine",
    "OCT": "octopamine",
}

# Neurotransmitter not (yet) determined. Not part of NEURO_TRANSMITTER_NAMES, which lists
# the transmitters that can be predicted.
NT_UNKNOWN = "UNKNOWN"


# Every value a connection can carry: the transmitters that can be predicted, then unknown. Lists that let a
# user pick a transmitter use this, so that unknown (all connections, until a curated table exists) can be
# picked too.
NEURO_TRANSMITTER_CHOICES = {
    **NEURO_TRANSMITTER_NAMES,
    NT_UNKNOWN: "unknown (not yet determined)",
}


def lookup_nt_type(txt):
    if txt:
        if txt.upper() in NEURO_TRANSMITTER_NAMES:
            return txt.upper()
        if txt.upper() == NT_UNKNOWN:
            return NT_UNKNOWN
        txt_low = txt.lower()
        for k, v in NEURO_TRANSMITTER_NAMES.items():
            if v.startswith(txt_low):
                return k
    return txt


def lookup_nt_type_name(txt):
    nt_type = lookup_nt_type(txt)
    return NEURO_TRANSMITTER_NAMES.get(nt_type, "unknown NT type")
