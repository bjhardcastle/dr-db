
class Config(pydantic.BaseModel):
    folder: str
    project: Literal["DynamicRouting", "TempletonPilotSession"] = pydantic.Field(
        default="DynamicRouting",
        description="Project name: DynamicRouting or TempletonPilotSession",
    )
    session_type: Literal["ephys", "behavior_with_sync"] = pydantic.Field(
        default="ephys", description="Type of session: ephys or behavior_with_sync"
    )
    ephys_day: Optional[int] = pydantic.Field(
        default=None, description="Day of ephys recording (starting at 1)", gt=0
    )
    perturbation_day: Optional[int] = pydantic.Field(
        default=None,
        description="Day of opto or injection perturbation (starting at 1)",
        gt=0,
    )
    is_production: bool = pydantic.Field(
        default=True,
        description="Production quality data; experimental variants are ok (False: dev testing, training operators)",
    )
    is_split_recording: bool = pydantic.Field(
        default=False,
        description="Split recording session: will not be uploaded yet (recordings to be concatenated later)",
    )
    is_context_naive: bool = pydantic.Field(
        default=False,
        description="Subject was not trained on stage 3 before first experiment",
    )
    is_injection_perturbation: bool = pydantic.Field(
        default=False, description="Injection perturbation or control session"
    )
    is_opto_perturbation: bool = pydantic.Field(
        default=False, description="Optogenetic perturbation or control session"
    )
    is_deep_insertion: bool = pydantic.Field(
        default=False,
        description="At least one probe has a surface channel recording",
    )
    probe_letters_to_skip: Optional[str] = pydantic.Field(
        default="",
        description="Probe letters to skip from upload/processing (e.g. 'ABC', [A-F], max 6 chars). Not necessary to list probes that were disabled in Open Ephys",
    )
    surface_recording_probe_letters_to_skip: Optional[str] = pydantic.Field(
        default="",
        description="Probe letters to skip from surface channel processing (e.g. 'ABC', [A-F], max 6 chars). Not necessary to list probes that were disabled in Open Ephys",
    )

    @pydantic.field_validator(
        "probe_letters_to_skip",
        "surface_recording_probe_letters_to_skip",
        mode="before",
    )
    def cast_to_upper_case(cls, v):
        return v.upper() if isinstance(v, str) else v

    @pydantic.field_validator(
        "probe_letters_to_skip",
        "surface_recording_probe_letters_to_skip",
        mode="after",
    )
    def validate_probe_letters(cls, v):
        if v and not re.fullmatch(r"[A-F]{0,6}", v):
            raise ValueError("Probe letters must be A-F only, up to 6 characters")
        return v

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        session_type = data.pop("session_type")
        project = data.pop("project")
        folder = data.pop("folder")
        return {
            session_type: {
                project: [
                    {
                        f"{PROJECT_PATHS[project]}/{folder}": {
                            "ephys_day": self.ephys_day,
                            "session_kwargs": {
                                k: v
                                for k, v in data.items()
                                if v is not None
                                and v != self.model_fields[k].default
                                and k not in ("ephys_day", "perturbation_day")
                            },
                        }
                    }
                ]
            }
        }

    def to_yaml_text_snippet(self) -> str:
        d = self.to_dict()
        indent = " " * 4
        session_dir_parent = PROJECT_PATHS[self.project] + "/"
        s = f"\n{indent}- {session_dir_parent}{self.folder}:"
        for attr in (
            "ephys_day",
            "perturbation_day",
        ):
            if value := getattr(self, attr, None):
                s = s + "\n" + indent * 2 + f"{attr}: {value}"
        session_kwargs = next(
            iter(next(iter(d[self.session_type][self.project])).values())
        )["session_kwargs"]
        if session_kwargs:
            s = s + "\n" + indent * 2 + "session_kwargs:"
            for k, v in session_kwargs.items():
                s = s + "\n" + indent * 3 + f"{k}: {v}"
        if s.endswith(":"):
            s = s[:-1]
        s = s.replace("\n\n", "\n")
        return (
            s
            + "\n"
            + (
                indent
                if (self.project == "DynamicRouting" and self.session_type == "ephys")
                else ""
            )
        )

