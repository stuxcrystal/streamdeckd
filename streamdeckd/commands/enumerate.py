from streamdeckd.devices import get_default_source


def main():
    dvmgr = get_default_source()
    for deck in dvmgr.enumerate():
        deck.open()

        layout = deck.key_layout()
        print(f"{deck.get_serial_number()} - {deck.deck_type()} {layout[0]}x{layout[1]}keys ({deck.id().decode('utf-8')})")

        deck.close()