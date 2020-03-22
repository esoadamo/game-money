function Comm() {
    const sockProto = location.protocol.toLowerCase().startsWith('https') ? 'wss' : 'ws';
    const sockURL = `${sockProto}://${location.host}/soc`;

    const sock = new WebSocket(sockURL);
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
            console.debug('<- ', data);
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
        console.debug('-> ', data);

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
