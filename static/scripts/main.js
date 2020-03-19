function askText(message) {
    return new Promise(resolve => resolve(prompt(message)));
}



function processMessage(type, msg) {
    switch (type) {
        case 'register':
            localStorage.setItem('gameMoneyId', msg);
            break;
    }
}

// Chronological code


window.addEventListener('load', () => {
    const renderer = new Renderer({playerName: 'Adamek', hero: true}, {input: 'Muj input'});
    renderer.render();
    const comm = new Comm();
    comm.onMessage = processMessage;

    return;

    let localId = localStorage.getItem('gameMoneyId');
    if (localId === null) {
        askText("Enter your name").then(name => {
            comm.send("register", name);
        })
    }
});