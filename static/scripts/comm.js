function Comm() {
    const sockProto = location.protocol.toLowerCase().startsWith('https') ? 'wss' : 'ws';
    const sockURL = `${sockProto}://${location.host}/soc`;

    const sock = new WebSocket(sockURL);
    const unsentMessages = [];

    let _connectionLost = false;
    let _pingTimeout = null;

    const connectionLost = () => {
        if (_connectionLost)
            return;
        _connectionLost = true;

        $('#modalConnectionLost').modal({'backdrop': 'static'});

        function reconnect() {
            const sock2 = new WebSocket(sock.url);
            sock2.onopen = () => location.reload();
            sock2.onerror = () => setTimeout(() => reconnect());
        }

        reconnect();
    };

    const ping = () => {
        if (_pingTimeout !== null)
            clearTimeout(_pingTimeout);
        setTimeout(() =>  {
            this.send('ping', 'ping');
            _pingTimeout = setTimeout(() => connectionLost(), 3000);
        }, (Math.random() * 3000) + 2000);
    };

    sock.onopen = () => {
        this.opened = true;
        this.onOpen();

        ping();

        while (unsentMessages.length > 0 && this.opened) {
            this.sendRaw(unsentMessages.pop());
        }
    };

    sock.onclose = () => {
        this.opened = false;
        this.onClose();
    };

    sock.onerror = connectionLost;

    sock.onmessage = (msg) => {
        let data;
        try {
            data = JSON.parse(msg.data);
            console.debug('<- ', data);
        } catch {
            return;
        }

        if (data.type === 'pong') {
            ping();
            return;
        }

        if (data.type.endsWith('ERR')) {
            new Popup(data.message, 5000).show();
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
