from posture_guardian import config, storage
from posture_guardian.dashboard import show_dashboard


def main() -> None:
    conn = storage.init_db(config.DB_PATH)
    show_dashboard(conn)
    conn.close()


if __name__ == "__main__":
    main()
