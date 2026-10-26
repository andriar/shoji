# Login screen (greetd + ReGreet)

Shoji can dress the login screen in your palette: the ink wallpaper behind a small panel, the
same fonts, the accent on the login button. It runs as [ReGreet](https://github.com/rharish101/ReGreet)
inside [cage](https://github.com/cage-kiosk/cage), started by [greetd](https://git.sr.ht/~kennylevinsen/greetd).

This replaces your display manager (GDM, SDDM, LightDM). Shoji never does that for you: the
steps below are yours to run, and the way back is at the end.

## 1. Make the files

```sh
shoji greeter
```

It writes `regreet.toml`, `regreet.css`, `background.png` and an example `config.toml` to
`~/.local/share/shoji/greeter/`, in the palette you use now, and prints the copy commands.
Run it again after you change palette; the login screen does not follow on its own (it runs as
another user and cannot read your home).

## 2. Install greetd, cage and ReGreet

Arch:

```sh
sudo pacman -S greetd greetd-regreet cage
```

Ubuntu 24.04 / Debian: greetd and cage are packaged, ReGreet is not.

```sh
sudo apt install greetd cage libgtk-4-dev build-essential cargo
cargo install --locked --git https://github.com/rharish101/ReGreet
sudo install -m755 ~/.cargo/bin/regreet /usr/local/bin/regreet
```

ReGreet keeps its cache and log in two folders the greeter user must own (`greeter` on Arch,
`_greetd` on Debian/Ubuntu):

```sh
sudo install -d -o greeter -g greeter /var/lib/regreet /var/log/regreet     # Arch
sudo install -d -o _greetd -g _greetd /var/lib/regreet /var/log/regreet     # Debian/Ubuntu
```

## 3. Copy Shoji's files into place

The commands `shoji greeter` printed:

```sh
G=~/.local/share/shoji/greeter
sudo install -Dm644 $G/regreet.toml $G/regreet.css -t /etc/greetd/
sudo install -Dm644 $G/background.png /etc/greetd/shoji-background.png
sudo install -d /usr/local/share/fonts/shoji
sudo cp ~/.local/share/fonts/Shoji/*.ttf /usr/local/share/fonts/shoji/ && sudo fc-cache -f
```

Then `/etc/greetd/config.toml`: take `$G/config.toml`, and on Debian/Ubuntu change
`user = "greeter"` to `user = "_greetd"`.

## 4. Switch (the step that changes your login)

Before you switch, know your way in without a login screen: Ctrl+Alt+F3 gives a text login.

```sh
sudo systemctl disable gdm3      # or sddm / lightdm: whichever you have
sudo systemctl enable greetd
```

The new screen shows at the next boot.

## The way back

From the desktop, or from a text login (Ctrl+Alt+F3):

```sh
sudo systemctl disable greetd
sudo systemctl enable gdm3
```

then reboot. The files in `/etc/greetd` can stay; nothing reads them once greetd is off.
