// noinspection JSUnusedLocalSymbols
let loginComplete = (comm, renderer) => {};

window.addEventListener('load', () => {
    const comm = new Comm();
    const renderer = new Renderer();
    comm.onMessage = basicMessages;

    function basicMessages(type, msg) {
        switch (type) {
            case 'register':
                console.log('registered as', msg);
                localStorage.setItem('gameMoneyId', msg);
                comm.send('login', msg);
                break;
            case 'login':
                renderer.variables.playerName = msg;
                loginComplete(comm, renderer);
                break;
            case 'unknownUser':
                localStorage.removeItem('gameMoneyId');
                location.reload();
                break;
        }
    }

    let localId = localStorage.getItem('gameMoneyId');
    if (localId === null) {
        askText("Enter your name").then(name => {
            comm.send("register", name);
        })
    } else {
       comm.send('login', localId);
    }
});