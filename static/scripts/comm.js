function Comm() {
    const sock = new WebSocket('ws://localhost:5000/soc'); // TODO socket URL
    const unsentMessages = [];

    sock.onopen = () => {
        this.opened = true;
        this.onOpen();

        while (unsentMessages.length > 0 && this.opened) {
            this.sendRaw(unsentMessages.pop());
        }
    };

    sock.onclose = () => {
        this.opened = false;
        this.onClose();
    };

    sock.onmessage = (msg) => {
        let data;
        try {
            data = JSON.parse(msg.data);
        } catch {
            return;
        }
        this.onMessage(data.type, data.message);
    };

    this.opened = false;

    this.onOpen = () => {
    };
    this.onClose = () => {
    };

    this.sendRaw = (data) => {
        if (!this.opened) {
            unsentMessages.push(data);
            return false;
        }

        sock.send(JSON.stringify(data));
        return true;
    };

    this.send = (type, message) => {
        return this.sendRaw({type, message});
    };

    // noinspection JSUnusedLocalSymbols
    this.onMessage = (type, message) => {
    };
}
