function askText(message) {
    return new Promise(resolve => resolve(prompt(message)));
}

let loginComplete = (comm, renderer) => {};

window.addEventListener('load', () => {
    const comm = new Comm();
    const renderer = new Renderer();
    comm.onMessage = processMessage;

    function processMessage(type, msg) {
        switch (type) {
            case 'register':
                console.log('registered as', msg);
                localStorage.setItem('gameMoneyId', msg);
                comm.send('login', msg);
                break;
            case 'login':
                renderer.variables.playerName = msg;
                loginComplete(comm, renderer);
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