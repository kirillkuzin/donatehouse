import configparser


def read_ch_config(filename='setting.ini'):
    """ (str) -> dict of str
    Read Config
    """
    config = configparser.ConfigParser()
    config.read(filename)
    if "Account" in config:
        return dict(config['Account'])
    return dict()


def write_ch_config(user_id,
                    user_token,
                    user_device,
                    channel_id,
                    language,
                    filename='setting.ini'):
    """ (str, str, str, str) -> bool
    Write Config. return True on successful file write
    """
    config = configparser.ConfigParser()
    config["Account"] = {
        "user_device": user_device,
        "user_id": user_id,
        "user_token": user_token,
        "channel_id": channel_id,
        "language": language,
    }
    with open(filename, 'a') as config_file:
        config.write(config_file)
    return True


def read_da_config(filename='setting.ini'):
    """ (str) -> dict of str
    Read Config
    """
    config = configparser.ConfigParser()
    config.read(filename)
    if "DA" in config:
        return dict(config['DA'])
    return dict()


def write_da_config(client_id,
                    client_str,
                    filename='setting.ini'):
    """ (str, str, str, str) -> bool
    Write Config. return True on successful file write
    """
    config = configparser.ConfigParser()
    config["DA"] = {
        "client_id": client_id,
        "client_secret": client_str,
    }
    with open(filename, 'a') as config_file:
        config.write(config_file)
    return True
