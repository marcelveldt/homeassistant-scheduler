# homeassistant-scheduler
A basic scheduler integration for HomeAssistant

This component is fully functional but needs some testing and user feedback before submitting it to Home Assistant core.

## Installation
- Copy the schedules folder into your custom_components subfolder of your Home Assistant config dir.
- Go to Integrations and enable the Schedules integration.
- Optionally provide a workday sensor entity.
- Create/add/update schedules through service calls.

## How does it work ?
- With this components you can define schedules, basically these are just routines/timeblocks.
For example a schedule called "workday morning" which is active when the day is morning and the state of the workday sensor is True.

- For each schedule there's a binary sensor created. You can very easy check the state with tools you already understand in HomeAssistant.

- A schedule has a before and after property which can be filled with either time (e.g. 22:00:00) of a sun notation (sunrise + 01:00:00).

- A schedule also has a condition, which accepts templating. For example the state of the workday sensor must be true.

- You can add/update/remove schedules through service calls.


