function closeWindow() {
    const url = "http://localhost:5842/shutdown";
    const xhttp = new XMLHttpRequest();
    xhttp.open("GET", url);
    xhttp.send();
}
