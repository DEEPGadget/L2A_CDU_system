"""MCG - Modbus Control Gateway (single-thread Python controller).

See docs/MCG.md and .claude/plans/ for the implementation plan. Skeleton only
at this point; modules will be filled in step by step:

    main.py          # entrypoint
    main_loop.py     # while loop: pubsub drain -> mode -> manual -> poll -> auto
    modbus_client.py # PCB Modbus RTU wrapper
    polling.py       # PCB read -> Redis SET (real flow, 4 branch + 2 loop)
    controller.py    # Auto fan curve + pump fixed (Stage 1)
    duty_mapper.py   # ui_duty <-> pump PWM (UI 0=stop@12%, 1-100->17-85%, clamp[170,850])
    redis_keys.py    # all redis key constants
    env_sensors.py   # ambient temp/humidity via I2C
"""
