async function login() {

    const username =
        document.getElementById(
            "username"
        ).value;

    const password =
        document.getElementById(
            "password"
        ).value;

    const formData =
        new URLSearchParams();

    formData.append(
        "username",
        username
    );

    formData.append(
        "password",
        password
    );

    const response = await fetch(
        "http://127.0.0.1:8000/login",
        {
            method: "POST",

            headers: {
                "Content-Type":
                "application/x-www-form-urlencoded"
            },

            body: formData
        }
    );

    const data =
        await response.json();

    if (data.access_token) {

        localStorage.setItem(
            "token",
            data.access_token
        );
        localStorage.setItem(
    "username",
    username
);
        window.location.href =
            "index.html";

    } else {

        document.getElementById(
            "message"
        ).innerText =
            "Login Failed";
    }
}
